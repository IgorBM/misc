import pytest
import os, re, shutil, subprocess, traceback, copy, time, datetime
from os.path import basename
from ofed_utils import *
from netaddr import *
import logging
from threading import Timer

# logging.basicConfig(filename='%s.log' % basename(__file__).split('.')[0],
#                     filemode='w',
#                     format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s %(message)s',
#                     datefmt='%H:%M:%S',
#                     level=logging.DEBUG)

loggerServer = logging.getLogger('Server')
loggerClient = logging.getLogger('Client')

#=======================================
timer = None
SECONDS_TO_WAIT = 40

port = 5001

default_iperf_path = "/usr/bin"
default_iperf_path2 = "/usr/local/bin"

iperf_exec = ""
iperf_app = "iperf"

ib_device = None

system_version = None

previous_client_mode = ""
current_client_mode = ""

previous_server_mode = ""
current_server_mode = ""

# Dummy workaround for distingushing parametrized tests in logs
search_line = ""

success_expected = ".*1 packets transmitted\, 1 received\, 0. packet loss.*"
loss_expected = ".*0 packets transmitted\, 0 received\, \+1 errors.*"

loss_expected2= ".*1 packets transmitted\,\ 0 received\, \+1 errors\, 100. packet loss.*" 

#success_expected = ".*packets transmitted.*"
#loss_expected = ".*packets transmitted.*"

#success_escaped = re.escape(success_expected)
#loss_escaped = re.escape(loss_expected)
#success_regex = re.compile(success_escaped)
#loss_regex = re.compile(loss_escaped)

success_regex = re.compile(success_expected)
loss_regex = re.compile(loss_expected,re.DOTALL)
loss_regex2 = re.compile(loss_expected2,re.DOTALL)


#iperf_regex_multi = re.compile('\[SUM\].*(?:Bytes|bits)\s+(?P<throughput>\d*\.?\d+)\s+.*$')
iperf_regex_multi = re.compile('\[SUM\].*(?:Bytes|bits)\s+(?P<throughput>\d*\.?\d+)\s+')
#=======================================
def setup_module(module):
    loggerClient.info('Set up test module %s' % module.__name__)

    try:
        """
         Setup step 1
            Check if IB ports are Up and choose default IB interface to work with 
        """
        global ib_device
        ib_device, err_msg = default_ib_device()

        if not ib_device:
            pytest.fail(err_msg)

        loggerClient.debug('Using %s as a default IB device' % ib_device)
        """
         Setup step 2
            Check if IP addresses are configured
        """
        if not ofed_server_ip[ib_device]:
            pytest.fail('Setup: Server host has no configured InfiniBand %s interface!' % ib_device)

        if not ofed_client_ip[ib_device]:
            pytest.fail('Setup: Client host has no configured InfiniBand %s interface!' % ib_device)

        loggerServer.debug('Setup: server host eth0 IP: %s' % ofed_server_ip['eth0'].ip)
        loggerServer.debug('Setup: server host %s IP: %s' % (ib_device, ofed_server_ip[ib_device].ip))

        loggerClient.debug('Setup: Client host %s IP: %s' % (ib_device, ofed_client_ip[ib_device].ip))

        """
         Setup step 3
        """ 
        # kill all previous processes (if any) on Client and on Server Hosts
        loggerClient.debug('Setup: wiping out all old testing tools processes')
        run(kill_cmd, shell=True)
        run('exec ssh -l root %s \'%s\'' % (ofed_server_ip['eth0'].ip,kill_cmd), shell=True)

        """
         Setup step 4
         Check current connection mode
        """
        cmd = 'cat /sys/class/net/%s/mode' % ib_device
        client_mode,err1 = run(cmd , shell=True) 
        server_mode,err1 = run("ssh -l root %s \'%s\'" % (ofed_server_ip['eth0'].ip,cmd), shell=True)
        
        """
         Setup step 5
            Remember current connection mode and set it to 'datagram'
        """

        if client_mode:
            # set it
            global previous_client_mode
            global current_client_mode
            previous_client_mode = client_mode
            current_client_mode = client_mode
            
        if server_mode:
            global previous_server_mode
            global current_server_mode
            previous_server_mode = server_mode
            current_server_mode = server_mode

        """
         Setup step 6
            Determine where is iperf
        """
        #Get environment variables:
        global default_iperf_path
        default_iperf_path = get_env('IPERF_EXEC_PATH', default_iperf_path) 
        global iperf_exec
        iperf_exec = "%s/%s" % ( default_iperf_path , iperf_app)

        if not os.path.exists(iperf_exec):
            global iperf_exec
            iperf_exec = "%s/%s" % ( default_iperf_path2 , iperf_app)

        """
         Setup step 7
            Find out OS release version
        """
        global system_version
        system_version = os_release()


    finally:
        pass

def teardown_module(module):
    loggerClient.info('Teardown of test module %s' % module.__name__)
    """
     Teardown step 1
        Restore previous connection mode to 
    """

    if previous_client_mode != current_client_mode:
        # set it back
        set_connection_mode(ib_device, previous_client_mode)

    if previous_server_mode != current_server_mode:
        # set it back
        remote_set_connection_mode(ib_device, previous_server_mode)


def setup_function(function):

    if (function.__name__ == 'test_mtu_iperf'):
        maximize_performance()
    

def teardown_function(function): 

    if timer:
        timer.cancel()

    if (function.__name__ == 'test_mtu_iperf'):
        revert_performance()
        
    loggerClient.info('##################################################')
    loggerClient.info('             Finished %s' % function.__name__)
    loggerClient.info('##################################################')

"""
MTU tests
"""

mtu_test_cases = [ 
          # mode      #MTU   #Expected error  # Test type
        ( "datagram", "1000", "", "" ),
        ( "datagram", "2000", "", "" ),
        #
        # setting MTU 3000 in datagram mode does not change actual MTU 2044 
        # and does not invoke "Invaliad argument" error message
        # so this test is commented out
        #
        # ( "datagram", "3000", "Invalid argument", "negative" ),  
        #
        ( "datagram", "4500", "Invalid argument", "negative" ),        
        ( "connected", "1000", "", "" ),    
        ( "connected", "70000", "Invalid argument", "negative" ),
    ]

mtu_test_cases_dict = dict([( '%s/MTU %s' % (tc[0],tc[1]), tc ) for tc in mtu_test_cases])

mtu_static_test_cases_dict = { 
                        # mode      MTU           Expected
    "test case 6" : ( "connected", "10000", "" ),
    "test case 7" : ( "connected", "min", "" ),
    "test case 8" : ( "connected", "random", "" ),
    "test case 9" : ( "connected", "65000", "" ),    
    "test case 10" : ( "connected", "70000", "Invalid argument" ),
    "test case 11" : ( "connected",  "AAA", "" ),  
}

mtu_iperf = [ 500, 1000, 2030]

"""
 fixture with test_cases disctionary as input parameters for test_netpipe function
"""
@pytest.fixture(scope="function", params=mtu_test_cases_dict.keys() )
def mtu_options(request):
    """
    Mark log files: out test has begun!
    """
    loggerClient.info('##################################################')
    loggerClient.info(' Starting a test in %s mode and MTU size %s' % (mtu_test_cases_dict[request.param][0], mtu_test_cases_dict[request.param][1]))
    loggerClient.info('##################################################')

    global search_line
    search_line = 'In a test with %s mode and MTU size %s' % (mtu_test_cases_dict[request.param][0], mtu_test_cases_dict[request.param][1])
    run('logger -t pytest "%s"' % search_line, shell=True)

    search_line = re.escape(search_line)

    new_keys = ['mode', 'MTU', 'expected', 'type' ]   
    return dict(zip(new_keys,mtu_test_cases_dict[request.param]))

#@pytest.mark.skipif('True')
def test_mtu_ping(mtu_options):

    mode = mtu_options['mode']
    mtu = mtu_options['MTU']
    mtu_expected = mtu_options['expected']

    """
     Test step 1
        Check the current connection mode and set it if required
    """
    if current_client_mode != mode:
        loggerClient.debug("Set client mode to: %s" % mode)
        set_connection_mode(ib_device,mode)
        global current_client_mode
        current_client_mode = mode

    if current_server_mode != mode:
        loggerServer.debug("Set server mode to: %s" % mode)
        remote_set_connection_mode(ib_device, mode)
        global current_server_mode
        current_server_mode = mode

    cmd = 'cat /sys/class/net/%s/mode' % ib_device
    loggerClient.debug("Verify client mode is set to: %s" % mode)
    client_mode,err1 = run(cmd , shell=True) 
    loggerClient.debug("Verify server mode is set to: %s" % mode)
    server_mode,err1 = run("ssh -l root %s \'%s\'" % (ofed_server_ip['eth0'].ip,cmd), shell=True)


    """
     Test step 2
        Set MTU and verify it's set
    """
    out_client = set_mtu(ib_device, mtu)
    out_server = remote_set_mtu(ib_device, mtu)

    if mtu_expected:
        assert mtu_expected in out_client, "Unable to get \"%s\" in client output while setting MTU above maximum" % mtu_expected
        assert mtu_expected in out_server, "Unable to get \"%s\" in server output while setting MTU above maximum" % mtu_expected
        
        return
    
    time.sleep(2)

    mtu_client  = get_mtu(ib_device)
    mtu_server = remote_get_mtu(ib_device)

    if (mtu_client != mtu) and (mtu_server != mtu):
        loggerClient.error("Unable to set mtu")
        pytest.fail("Unable to set mtu")

    time.sleep(1)
    """
     Test step 3
        Ping command with  data size smaller than MTU and verify it
    """
    cmd ="ping -M do -c 1 -s %d -I %s %s" % (int(mtu)-50,ib_device, ofed_server_ip[ib_device].ip )
    ping_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    ping1_out, ping1_err = ping_proc.communicate()
    loggerClient.debug("Ping command with  data size smaller than MTU:")
    log("Output of %s:" % cmd, ping1_out)
    if ping1_err:
        log("Errors:", ping1_err)

    if mtu_options['type'] == 'negative': 
        assert re.search(loss_regex,ping1_out), "Unable to find in ping output that packets were not transmitted"     
        #assert ping1_out.count(success), "Unable to find in ping output that packets were not transmitted"     
    else:
        assert re.search(success_regex, ping1_out), "Unable to find transmitted packets in ping output" 
        #assert ping1_out.count(ping1_expected), "Unable to find transmitted packets in ping output" 

    """
     Test step 4
        Ping command with  data size larger than MTU and verify it
    """
    cmd2 ="ping -M do -c 1 -s %d -I %s %s" % (int(mtu)+50,ib_device, ofed_server_ip[ib_device].ip )
    ping2_proc = subprocess.Popen(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    ping2_out, ping2_err = ping2_proc.communicate()
    loggerClient.debug("Ping command with  data size larger than MTU:")
    log("Output of %s:" % cmd2, ping2_out)
    if ping2_err:
        log("Errors:", ping2_err)

    assert (re.search(loss_regex,ping2_out) or re.search(loss_regex2,ping2_out)), "Unable to find in ping output that packets were not transmitted" 


@pytest.fixture(scope="function", params=["10", "random", "65520", "70000"])
def static_mtu(request):

    loggerClient.info('##################################################')
    loggerClient.info(' Starting test static MTU == %s' % request.param)
    loggerClient.info('##################################################')

    if request.param == "random":
        import random
        return str(random.randint(0, 65519))
    else:
        return request.param

#@pytest.mark.skipif('True')
def test_static_mtu(static_mtu):

    """
     Test step 1
        Check the current connection mode and set it if required
    """
    mode = "connected"
    set_connection_mode(ib_device,mode, use_config=True)
    global current_client_mode
    current_client_mode = mode

    remote_set_connection_mode(ib_device, mode, use_config=True)
    global current_server_mode
    current_server_mode = mode


    # if current_client_mode != mode:
    #     loggerClient.debug("Set client mode to: %s" % mode)
    #     set_connection_mode(ib_device,mode, use_config=True)
    #     global current_client_mode
    #     current_client_mode = mode

    # if current_server_mode != mode:
    #     loggerServer.debug("Set server mode to: %s" % mode)
    #     remote_set_connection_mode(ib_device, mode, use_config=True)
    #     global current_server_mode
    #     current_server_mode = mode

    cmd = 'cat /sys/class/net/%s/mode' % ib_device
    loggerClient.debug("Verify client mode is set to: %s" % mode)
    client_mode,err1 = run(cmd , shell=True) 
    loggerClient.debug("Verify server mode is set to: %s" % mode)
    server_mode,err1 = run("ssh -l root %s \'%s\'" % (ofed_server_ip['eth0'].ip,cmd), shell=True)


    """
     Test step 2
        Set MTU and verify it's set
    """
    set_static_mtu(ib_device, static_mtu)

    """
     Verification step 1
        Verify MTU is set
    """
    mtu_client  = get_mtu(ib_device)

    loggerClient.debug("Actual MTU: %s" % mtu_client)
    
    if int(static_mtu) > 65520:
        assert int(mtu_client) == 65520, "MTU is not equal to default maximum value while setting MTU above maximum"
        return
    else:
        assert int(mtu_client) == int(static_mtu), "Unable to set mtu"


@pytest.fixture(scope="function", params=["datagram","connected"])
def mode(request):

    loggerClient.info('##################################################')
    loggerClient.info(' Starting  MTU iperf test for %s mode.' % request.param)
    loggerClient.info('##################################################')

    return request.param

#@pytest.mark.skipif('True')
def test_mtu_iperf(mode):

    throughput = []
 
    set_connection_mode(ib_device,mode)

    for mtu in mtu_iperf:

        """
         Test step 1
            Set MTU on client and server
        """

        out_client = set_mtu(ib_device, mtu)
        out_server = remote_set_mtu(ib_device, mtu)

        time.sleep(3)

        mtu_client  = get_mtu(ib_device)
        mtu_server = remote_get_mtu(ib_device)

        if (mtu_client != str(mtu)) or (mtu_server != str(mtu)):
            loggerClient.error("Unable to set mtu")
            pytest.fail("Unable to set mtu")

        time.sleep(2)
        """
         Test step 2
            Start iperf  command as a server
        """
        cmd = "ssh -t -l root %s \'%s -f M -s -p %s\'" % (ofed_server_ip['eth0'].ip, iperf_exec, port)
        loggerServer.debug("Starting iperf server: %s" % cmd)
        server_proc = subprocess.Popen( cmd, 
                                                    stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE, 
                                                    shell=True)
        time.sleep(3)                                                 
        server_proc.poll()
        if server_proc.returncode != None:
            out, err = server_proc.communicate()
            log("Server command output:", out, writer=lambda s: loggerServer.debug(s))
            log("Server command stderr output:", err, writer=lambda s: loggerServer.debug(s))
            pytest.fail("Failed to start iperf server")

        """
         Test step 3
         Start iperf command as a client
        """
        cmd = "%s -w 16M -f M -c %s -p %s -t 30 -P 10 -d" % (iperf_exec, ofed_server_ip[ib_device].ip, port)
        loggerClient.debug("Starting iperf client: %s" % cmd)
        global port
        port += 1

        client_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)  
        """
         Test step 4
         get iperf outputs and put it into a test log
        """
        def kill_client_proc():
            try:
                client_proc.kill()
                server_proc.kill()
                loggerClient.error('***** Terminated client and server processes after timeout is expired!')
            except OSError:
                pass
        
        global timer
        timer = Timer(SECONDS_TO_WAIT, kill_client_proc)
        timer.start()

        try: 
            client_out, client_err = client_proc.communicate()
        finally:
            timer.cancel()

        # Give some time for SDP logger
        time.sleep(5) 

        log("Client iperf command output:", client_out)

        server_proc.kill()
        server_out, server_err = server_proc.communicate()
        log("Server iperf command output:", server_out, writer=lambda s: loggerServer.debug(s))

        """
         Test step 5
         finish iperf process on server host, so /var/log/libsdp.log is populated with data
        """
        run('ssh -l root %s \'killall iperf\'' % ofed_server_ip['eth0'].ip, shell=True)


        """
         Test results verification step 1:
            Find iperf SUM values in its results output and populate a list
        """ 

        match = re.search(iperf_regex_multi, client_out)
        if match:
            throughput.append(float(match.groupdict()['throughput']))
            loggerClient.debug("Found: %s" % match.groups() )
        #match = re.finditer(iperf_regex_multi, client_out)
        # count = 0
        # for m in match:
        #     count += 1
        #     res = m.groupdict()
        #     throughput.append(float(res['throughput']))
        else:
            loggerServer.debug("Unable to find iperf output for MTU: %s" % mtu)

    print throughput
    print sorted(throughput)
    assert throughput == sorted(throughput) , "Iperf throughput increment is not monotonously increasing while MTU size is increased in range from min to max supported value"
