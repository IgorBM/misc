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
SECONDS_TO_WAIT = 240

global port
port = 6001

# Dummy workaround for distingushing parametrized tests in logs
search_line = ""

system_version = None
# cpupower_status = "inactive"
# cpupower_status_cmd = "systemctl status cpupower| grep -e '\sactive'"

arch = None
#=======================================
def setup_module(module):
    loggerClient.info('Set up test module %s' % module.__name__)

    try:
        """
         Setup step 1
        """
        if not ofed_server_ip['ib0']:
            pytest.fail('Setup: Peer host has no configured InfiniBand ib0 interface!')

        #if not ofed_server_ip['ib1']:
        #    pytest.fail('Setup: Peer host has no configured InfiniBand ib1 interface!')

        if not ofed_client_ip['ib0']:
            pytest.fail('Setup: Local host has no configured InfiniBand ib0 interface!')

        loggerServer.debug('Setup: Server host eth0 IP: %s' % ofed_server_ip['eth0'].ip)
        loggerServer.debug('Setup: Sserver host ib0 IP: %s' % ofed_server_ip['ib0'].ip)
        #loggerServer.debug('Setup: Server host ib1 IP: %s' % ofed_server_ip['ib1'].ip)

        loggerServer.debug('Setup: Client host ib0 IP: %s' % ofed_client_ip['ib0'].ip)

        """
         Setup step 2 
        """ 
        # kill all previous processes (if any) on Client and on Server Hosts
        loggerClient.debug('Setup: wiping out all old testing tools processes')
        run("exec " + kill_cmd, shell=True)
        run('exec ssh -l root %s \'exec %s\'' % (ofed_server_ip['eth0'].ip,kill_cmd), shell=True)

        """
         Setup step 3
        """
        #Find out if it OL5 or OL6 or OL7
        global system_version
        system_version = os_release()

        
    finally:
        pass

def teardown_module(module):
    loggerClient.info('Teardown of test module %s' % module.__name__)

def setup_function(function):

    if (function.__name__ == 'test_perftest') or (function.__name__ == 'test_rdma_verbs'):
        maximize_performance()

        # kill all previous pingpong processes (if any) on Client and on Server Hosts
        loggerClient.debug('Teardown function: wiping out previous pingpong processes')
        #kill_ibverbs_cmd = 'pgrep -f  ib\_.*\_|xargs kill -9'
        kill_ibverbs_cmd = 'if pgrep -f  ib\_.*\_ ; then pkill -f  ib\_.*\_ ; fi'
        run("exec " + kill_ibverbs_cmd, shell=True)
        run('exec ssh -l root %s \'%s\'' % (ofed_server_ip['eth0'].ip,kill_ibverbs_cmd), shell=True)        


def teardown_function(function): 

    if timer:
        timer.cancel()

    if (function.__name__ == 'test_perftest') or (function.__name__ == 'test_rdma_verbs'):
        revert_performance()

        
    loggerClient.info('##################################################')
    loggerClient.info('             Finished %s' % function.__name__)
    loggerClient.info('##################################################')


# For UEK3 and greater.
perftest_testcases = {  
                            # perftest
                            "ib_read_bw" : "-a", 
                            "ib_read_lat" : "-a", 
                            "ib_send_bw" : "-a",
                            "ib_send_lat" : "-a",                  
                            "ib_write_bw" : "-a", 
                            "ib_write_lat" : "-a",
                            "ib_atomic_bw" : "-n 100", 
                            "ib_atomic_lat" : "-n 100"
                }

rdma_verbs_testcases = [   
                               # ("rdma_lat", "default", "default"), 
                               # ("rdma_lat", "4000", "2000") 

                               # From Jenny's email:
                               # rdma_lat is not included in the new user space package  perftest-3.0-0.0.1.el6.x86_64. 
                               # I installed perftest-2.0-2.el6.x86_64.rpm and saw the following. 
                               # # ls -al /usr/bin/rdma_lat
                               # lrwxrwxrwx. 1 root root 11 Jun 10 03:19 /usr/bin/rdma_lat -> ib_read_lat
                               # so using ib_read_lat here:
                                ("ib_read_lat", "default", "default"), 
                                ("ib_read_lat", "4000", "2000") 

                    ]

rdma_verbs_testcases_dict = dict([( tc[0]+':datasize='+tc[1]+',iterations='+tc[2] , tc ) for tc in rdma_verbs_testcases])

diagnostic_testcases = [  
                                # cmd, data_size, count (of packets to be sent)
                                ("rping -v -d", "default", "2"), 
                                ("udaddy", "default", "default"), 
                                ("udaddy", "10", "100"), 
                                ("udaddy", "2033", "10000"), 
                                ("udaddy", "4096", "10000"), 

                                # -v is depricated in UEK4 version of ucmatose
                                #("ucmatose -v -c 100", "10000", "10000"), 
                                #("ucmatose -v -c 100", "default", "default"), 
                                #("ucmatose -v", "10000", "10000"),
                                #("ucmatose -v", "4096", "10000")

                                ("ucmatose -c 100", "10000", "10000"), 
                                ("ucmatose -c 100", "default", "default"), 
                                ("ucmatose ", "10000", "10000"),
                                ("ucmatose ", "4096", "10000")

                    ]

diagnostic_testcases_dict = dict([( tc[0]+':datasize='+tc[1]+',count='+tc[2] , tc ) for tc in diagnostic_testcases])


"""
 fixture with test_cases disctionary as input parameters for test_netpipe function
"""
@pytest.fixture(scope="function", params=sorted(perftest_testcases.keys(),reverse=True) )
def perf_cmd(request):

    if ( 'OL5' in client_system_version) and request.param.startswith("ib_atomic"):
        pytest.xfail('ib_atomic* is not present on OL5')
    """
    Mark log files: out test has begun!
    """
    loggerClient.info('##################################################')
    loggerClient.info(' Starting perftest command: %s' % request.param)
    loggerClient.info('##################################################')

    global search_line
    search_line = 'In perftest test: %s' % request.param
    run('logger -t pytest "%s"' % search_line, shell=True)

    search_line = re.escape(search_line)

    # Format of perf_cmd dictionary:
    # "cmd", "cmd_param1"

    return dict( [ ('cmd',request.param), ('cmd_param1',perftest_testcases[request.param]) ] )


#@pytest.mark.skipif('True')
#@pytest.mark.skipif('%s' % (not is_uek3()))
@pytest.mark.skipif('%s' % is_on_sparc())
def test_perftest(perf_cmd):

    """
     Test step 1
       Start server command
    """
    # Format of perf_cmd dictionary:
    # "cmd", "cmd_param1"

    cmd_line = perf_cmd['cmd'] + ' -p ' + str(port) + ' ' + perf_cmd['cmd_param1']

    ssh_cmd = "ssh -l root %s \'%s 2>&1\'" % (ofed_server_ip['eth0'].ip, cmd_line)
    loggerServer.debug("Starting on server: %s" % cmd_line)
    server_proc = subprocess.Popen( ssh_cmd, 
                                                stdout=subprocess.PIPE, 
                                                stderr=subprocess.PIPE, 
                                                shell=True)
    time.sleep(5)                                                 
    server_proc.poll()
    if server_proc.returncode != None:
        out, err = server_proc.communicate()
        log("Server command output:", out, writer=lambda s: loggerServer.debug(s))
        log("Server command stderr output:", err, writer=lambda s: loggerServer.debug(s))
        pytest.fail("Can't start %s on server. %s" % (cmd_line, out) )

    """
     Test step 2
     Start a client command
    """

    cmd = "%s %s 2>&1" % (cmd_line, ofed_server_ip['ib0'].ip)
    loggerClient.debug("Starting on client: %s" % cmd)

    client_proc = subprocess.Popen("exec " + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)  

    global port
    port += 1

    """
     Test step 3
     trigger Timer() and avoid any hangs of executed commands
    """
    def kill_client_proc():
        try:
            client_proc.kill()
            server_proc.kill()
            loggerClient.error('***** Terminated client process after timeout is expired!')
        except OSError:
            pass

    global timer
    timer = Timer(SECONDS_TO_WAIT, kill_client_proc)
    timer.start()

    """
     Test step 4
     get outputs and put it into a test log
    """

    try: 
        client_out, client_err = client_proc.communicate()
    finally:
        timer.cancel()
    
    # Give some time for SDP logger
    time.sleep(5) 

    log("Client command output:", client_out)

    server_proc.kill()

    server_out, server_err = server_proc.communicate()
    log("Server command output:", server_out, writer=lambda s: loggerServer.debug(s))
    
    """
     Test results verification step 1:
        Evaluate transmission results
    """ 

    if re.match('.*Conflicting CPU frequency values detected.*',client_out): 
         pytest.fail("Conflicting CPU frequency values detected!Error in client and server host configurations!Find another hosts for test execution")        

    # when tests pass, test o/p statistics have to be non zero. 
    # For latency tests , value of fields  t_min[usec/iter],t_max[usec], t_typical[usec]
    # have to be non zero. For bandwidth tests , value of fields BW peak[MB/sec],BW average[MB/sec] 
    # have to be non zero.

    res_list = re.findall('\s\d+\s+\d+\s+(\d+\.?\d*|inf)\s+(\d+\.?\d*|inf)\s+(\d+\.?\d*|inf)', client_out) 

    for res in res_list:
        for r in res:
            if r=='inf':
                assert False, "For latency tests , value of fields  t_min[usec/iter],t_max[usec], t_typical[usec] have to be non zero."
            if r=='0.00':
                assert False, "For bandwidth tests , value of fields BW peak[MB/sec],BW average[MB/sec] have to be non zero"
            if r=='0.000000':
                assert False, "For bandwidth tests , value of fields BW MsgRate[Mpps] has to be non zero"

@pytest.fixture(scope="function", params=sorted(rdma_verbs_testcases_dict.keys()) )
def rdma_verbs_options(request):
    """
    Mark log files: out test has begun!
    """
    loggerClient.info('##################################################')
    loggerClient.info(' Starting  rdma verbs test: %s' % request.param)
    loggerClient.info('##################################################')

    global search_line
    search_line = 'In rdma verbs test: %s' % request.param
    run('logger -t pytest "%s"' % search_line, shell=True)

    search_line = re.escape(search_line)

    new_keys = ['cmd', 'data_size', 'iterations']
    return dict(zip(new_keys,rdma_verbs_testcases_dict[request.param]))


#@pytest.mark.skipif('True')
@pytest.mark.skipif('%s' % ( is_on_sparc() or ('OL7' in os_release() ) ) )
def test_rdma_verbs(rdma_verbs_options):
    """
    Test step 1
    Start server command
    """
    # Format of rdma_verbs_options:
    # "cmd", "data_size", "iterations"
    if rdma_verbs_options['data_size'] != 'default':
        rdma_verb_cmd = rdma_verbs_options['cmd'] + ' -s ' + rdma_verbs_options['data_size'] + ' -n ' + rdma_verbs_options['iterations']
    else:
        rdma_verb_cmd = rdma_verbs_options['cmd']

    rdma_verb_cmd = rdma_verb_cmd + ' -p ' + str(port)

    cmd = "ssh -l root %s \'%s 2>&1\'" % (ofed_server_ip['eth0'].ip, rdma_verb_cmd)
    loggerServer.debug("Starting on server: %s" % rdma_verb_cmd)
    server_proc = subprocess.Popen( cmd, 
                                                stdout=subprocess.PIPE, 
                                                stderr=subprocess.PIPE, 
                                                shell=True)
    time.sleep(5)                                                 
    server_proc.poll()
    if server_proc.returncode != None:
        out, err = server_proc.communicate()
        log("Server command output:", out, writer=lambda s: loggerServer.debug(s))
        log("Server command stderr output:", err, writer=lambda s: loggerServer.debug(s))
        pytest.fail("Can't start %s on server. %s" % (rdma_verb_cmd, out) )

    """
     Test step 2
     Start a client command
    """

    cmd = "%s %s 2>&1" % (rdma_verb_cmd, ofed_server_ip['ib0'].ip)
    loggerClient.debug("Starting on client: %s" % cmd)

    client_proc = subprocess.Popen("exec " + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)  

    global port
    port += 1
    
    """
     Test step 3
     trigger Timer() and avoid any hangs of executed commands
    """
    def kill_client_proc():
        try:
            client_proc.kill()
            server_proc.kill()
            loggerClient.error('***** Terminated client process after timeout is expired!')
        except OSError:
            pass
    
    global timer
    timer = Timer(SECONDS_TO_WAIT, kill_client_proc)
    timer.start()

    """
     Test step 4
     get outputs and put it into a test log
    """

    try: 
        client_out, client_err = client_proc.communicate()
    finally:
        timer.cancel()
    
    # Give some time for SDP logger
    time.sleep(5) 

    log("Client command output:", client_out)

    server_proc.kill()

    server_out, server_err = server_proc.communicate()
    log("Server command output:", server_out, writer=lambda s: loggerServer.debug(s))
    
    """
     Test results verification step 1:
        Evaluate transmission results
    """ 

    # when tests pass, test o/p statistics have to be non zero. 
    # For latency tests , value of fields  t_min[usec/iter],t_max[usec], t_typical[usec]
    # have to be non zero. 

    res_list = re.findall('\s\d+\s+\d+\s+(\d+\.?\d*|inf)\s+(\d+\.?\d*|inf)\s+(\d+\.?\d*|inf)', client_out)

    for res in res_list:
        for r in res:
            if r=='inf':
                assert False, "Value of fields  t_min[usec/iter],t_max[usec], t_typical[usec] have to be non zero."
            if r=='0.00':
                assert False, "Value of fields  t_min[usec/iter],t_max[usec], t_typical[usec] have to be non zero."
            if r=='0.000000':
                assert False, "Value of fields  t_min[usec/iter],t_max[usec], t_typical[usec] have to be non zero."




@pytest.fixture(scope="function", params=sorted(diagnostic_testcases_dict.keys()) )
def diag_options(request):
    """
    Mark log files: out test has begun!
    """
    loggerClient.info('##################################################')
    loggerClient.info(' Starting  Diagnistic test: %s' % request.param)
    loggerClient.info('##################################################')

    # kill all previous processes (if any) on Client and on Server Hosts
    loggerClient.debug('Setup: wiping out all old testing tools processes')
    kill_cmd = 'killall rds-stress NPtcp qperf rdma_lat rping udaddy ucmatose iperf; pkill "ibv_*_pingpong"'        
#    run("exec " + kill_cmd, shell=True)
    run('exec ssh -l root %s \'exec %s\'' % (ofed_server_ip['eth0'].ip,kill_cmd), shell=True)


    global search_line
    search_line = 'In Diagnistic test: %s' % request.param
    run('logger -t pytest "%s"' % search_line, shell=True)

    search_line = re.escape(search_line)

    new_keys = ['cmd', 'data_size', 'count']
    return dict(zip(new_keys,diagnostic_testcases_dict[request.param]))



def test_diagnostic(diag_options):

    # Workaround for SPARC: remove "-v" option from any command
    if is_on_sparc():
        diag_options['cmd'] = diag_options['cmd'].replace("-v", "")

    """
     Test step 1
       Start server command
    """
    # Format of options:
    # "cmd", "data_size", "count"
    if diag_options['data_size'] != 'default':
        diag_cmd = diag_options['cmd'] + ' -S ' + diag_options['data_size'] + ' -C ' + diag_options['count']
    else:
        diag_cmd = diag_options['cmd']
        if diag_options['count'] != 'default':
            diag_cmd = diag_cmd + ' -C ' + diag_options['count'];

    if diag_options['cmd'].count('rping') != 0:
        cmd = "ssh -l root %s \'exec %s -s 2>&1\'" % (ofed_server_ip['eth0'].ip, diag_cmd)
    else:
        cmd = "ssh -l root %s \'exec %s 2>&1\'" % (ofed_server_ip['eth0'].ip, diag_cmd)

    loggerServer.debug("Starting on server: %s" % cmd)
    server_proc = subprocess.Popen("exec " + cmd, 
                                                stdout=subprocess.PIPE, 
                                                stderr=subprocess.PIPE, 
                                                shell=True)
    time.sleep(5)                                                 
    server_proc.poll()
    if server_proc.returncode != None:
        out, err = server_proc.communicate()
        log("Server command output:", out, writer=lambda s: loggerServer.debug(s))
        log("Server command stderr output:", err, writer=lambda s: loggerServer.debug(s))
        pytest.fail("Can't start %s on server. %s" % (diag_cmd, out) )

    """
     Test step 2
     Start a client command
    """
    if diag_options['cmd'].count('rping') != 0:
        cmd = "%s -c -a %s 2>&1" % (diag_cmd, ofed_server_ip['ib0'].ip)
    else:
        cmd = "%s -s %s 2>&1" % (diag_cmd, ofed_server_ip['ib0'].ip)

    loggerClient.debug("Starting on client: %s" % cmd)

    client_proc = subprocess.Popen("exec " + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)  
    """
     Test step 3
     trigger Timer() and avoid any hangs of executed commands
    """
    def kill_client_proc():
        try:
            client_proc.kill()
            server_proc.kill()
            loggerClient.error('***** Terminated client process after timeout is expired!')
        except OSError:
            pass
    
    global timer
    timer = Timer(SECONDS_TO_WAIT, kill_client_proc)
    timer.start()

    """
     Test step 4
     get outputs and put it into a test log
    """

    try: 
        client_out, client_err = client_proc.communicate()
    finally:
        timer.cancel()
    
    # Give some time for SDP logger
    time.sleep(5) 

    log("Client command output:", client_out)

    server_proc.kill()

    server_out, server_err = server_proc.communicate()
    log("Server command output:", server_out, writer=lambda s: loggerServer.debug(s))

    """
     Test results verification step 1:
    """

    # Verifications for rping
    if diag_options['cmd'].count('rping') != 0:
        msgs_to_verify = [ 'RDMA_CM_EVENT_ESTABLISHED', 
                           'rmda_connect successful',
                           'RDMA_CM_EVENT_DISCONNECTED' ]

        for msg in msgs_to_verify:                           
            assert client_out.count(msg) , "Unexpected result.Unable to find event: %s while running command %s" % (msg,diag_options['cmd'])

        assert client_out.count('send completion') == 4 
        assert client_out.count('recv completion') == 4

    else: # for udaddy and ucmatose commands:

        finished_successfully = client_out.count('return status 0')

        if not finished_successfully:
            
            if diag_options['cmd'].count('ucmatose') != 0:
                # For ucmatose: check if expected non-0 return is occured when packet data size exceeds MTU 
                mtu = get_mtu('ib0')
                if (diag_options['data_size'] != 'default') and (int(diag_options['data_size']) > int(mtu)):
                    assert client_out.count('is larger than active mtu'), "Unexpected result: %s finished with different return code" % diag_options['cmd']
                else:
                    assert finished_successfully,  "Unexpected result: %s finished unsuccessfully " % diag_options['cmd'] 
            else:
                #For udaddy:  
                assert finished_successfully,  "Unexpected result: %s finished unsuccessfully " % diag_options['cmd'] 
            
