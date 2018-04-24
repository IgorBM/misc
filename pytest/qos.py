import pytest
import os, re, shutil, subprocess, traceback, copy, time, datetime
from os.path import basename
from ofed_utils import *
from netaddr import *
import logging

# logging.basicConfig(filename='%s.log' % basename(__file__).split('.')[0],
#                     filemode='w',
#                     format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s %(message)s',
#                     datefmt='%H:%M:%S',
#                     level=logging.DEBUG)

loggerServer = logging.getLogger('Server')
loggerClient = logging.getLogger('Client')

#=======================================

rds_server_proc = None

ib_device = None

#=======================================

rds_server_port=5001
rds_stress = "/usr/bin/rds-stress"
rds_conf_file = "/etc/modprobe.d/rds.conf"
rds_conf_file_backup = ""
rds_rdma_conf_file = "/etc/modprobe.d/rds_rdma.conf"
var_log = "/var/log/messages"

loggerClient.debug('RDS Config File: %s' % rds_conf_file)
loggerClient.debug('RDS RDMA Config File: %s' % rds_rdma_conf_file)


def setup_module(module):
    loggerClient.info('Set up test module %s' % module.__name__)

    try:
        """
         Setup step 1
            Check if IB ports are Up and choose default IB interface to work with 
        """
        global ib_device
        if is_on_guest():
            ib_device = 'ib0'
        else:
            ib_device, err_msg = default_ib_device()

        if not ib_device:
            pytest.fail(err_msg)
            
        loggerClient.debug('Using %s as a default IB device' % ib_device)
        """
         Setup step 2
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
        run("exec " + kill_cmd, shell=True)
        run('exec ssh -l root %s \'exec %s\'' % (ofed_server_ip['eth0'].ip,kill_cmd), shell=True)

        """
         Setup step 4
        """
        #loggerClient.debug('Setup: cleaning /var/log/messages before the test on both server and client hosts')
        #run('ssh -l root %s \'cat /dev/null > /var/log/messages\'' % ofed_server_ip['eth0'], shell=True)
        #run('cat /dev/null > /var/log/messages', shell=True)

        """
         Setup step 5
        """
        #global rds_conf_file_backup
        #rds_conf_file_backup = backup_config_file(rds_conf_file)
    finally:
        pass

def teardown_module(module):
    loggerClient.info('Teardown of test module %s' % module.__name__)
    # if (rds_conf_file_backup != ""):
    #     restore_config_file(rds_conf_file_backup, rds_conf_file)
    #     reload("rds")
    #     # TODO remove backup conf file

def setup_function(function):
    loggerClient.info('##################################################')
    loggerClient.info('              Starting %s' % function.__name__)
    loggerClient.info('##################################################')

  

def teardown_function(function): 

    if (function.__name__ == 'test_rds_stress'):
        global rds_server_port
        rds_server_port += 1
        # Re-init internal data structures
        rds_info_params['before']['server'].clear()
        rds_info_params['before']['client'].clear()
        rds_info_params['after']['server'].clear()
        rds_info_params['after']['client'].clear()
    
    loggerClient.info('##################################################')
    loggerClient.info('             Finished %s' % function.__name__)
    loggerClient.info('##################################################')


######################################################
# Where we store values of stat parameters during the tests:
######################################################
rds_info_params = {}

rds_info_params['before'] = {}
rds_info_params['before']['server'] = {}
rds_info_params['before']['client'] = {}

rds_info_params['after'] = {}
rds_info_params['after']['server'] = {}
rds_info_params['after']['client'] = {}

# Have all the assertions here, so the test verification part is comprehensible
def assertMessage( outputs , msg):
    regex = re.compile(re.escape(msg))
#    assert [ m.group(1) for m in (re.search(regex, lines) for lines in outputs) if m ], "Unexpected result.Unable to find message: %s in client or server output" % msg
    assert [ re.search(regex, lines) for lines in outputs ], "Unexpected result.Unable to find message: %s in client or server output" % msg

def assertValueIncreased(param, where):
    prev = rds_info_params['before'][where][param]
    now = rds_info_params['after'][where][param]
    assert int(prev) < int(now) ,  "Unexpected result.The value of %s does not increase on %s.\n It was %s and now it %s" % (param,where,prev,now)

def assertValueIncByOne(param, where):
    prev = rds_info_params['before'][where][param]
    now = rds_info_params['after'][where][param]
    assert ( int(now) - int(prev)) == 1  ,  "Unexpected result. The value of %s does not increase by 1 on %s.\n It was %s and now it %s" % (param,where,prev,now)


def _fetch_parameter(param, queue_val, where):

    # _fetch_parameter("NextTX",queue_val,'client')
    loggerClient.info('Going to fetch %s parameter on %s:' % (param, where) )

    
    if rds_info_params['before'] and (param in rds_info_params['before'][where]):
        when = 'after'
    else:
        when = 'before'

    if param == 'qos_threshold_exceeded':
        rds_info_params[when][where].update(fetch_stat_parameters('rds-info -c', [ param ]))
        return

    if param == 'NextTX':
        column_number = '4'
    elif param == 'NextRX':
        column_number = '5'
    else:
        pytest.fail("Unexpected parameter %s" % param)             

    rds_info_cmd = "rds-info -n | awk '{ if ($3 ~ /%s/) { print $%s; exit } }'" % (queue_val, column_number)

    if where == 'server':
        rds_info_cmd =  "ssh -l root %s \"%s\"" % (ofed_server_ip['eth0'].ip, rds_info_cmd.replace("$", "\$")) 

    value, err = run(rds_info_cmd, shell=True)
    if (value is not None) and value !="":
        rds_info_params[when][where].update( { param : value } )
    else:
        rds_info_params[when][where].update( { param : 0 } )
    #    pytest.fail("Unable to find the value of %s on %s" % (param,where)


    

"""
 fixtures with input configuration parameters
"""
@pytest.fixture(scope="function", params=[0, 1, 2, 3])
def configured_threshold(request):
    """
    Prepare rds_conf file with appropriate rds_qos_threshold value. 
    Which will be used for several runs of rds-stress command with 
    different data size and queus parameters 
    """
    out, err = run("grep rds_qos_threshold_action %s | awk -F= '{ print $2}'" % rds_conf_file, shell=True)
#    if (out == "") or int(out) != int(request.param):
    config_options = [  "options rds rds_qos_threshold_action=%s" % request.param, 
                        "options rds rds_qos_threshold=1:1K,2:1M"]
    #set_config(rds_conf_file, config_options)
    #remote_set_config(rds_conf_file, config_options)
    cmd = 'echo -e "%s" > %s' %  ('\n'.join(config_options), rds_conf_file)
    run("exec " + cmd, shell=True)
    run("ssh -l root %s \'%s\'" % (ofed_server_ip['eth0'].ip,cmd), shell=True)
    local_reload('rds', device=ib_device) 
    remote_reload('rds')        

#    else:
#        loggerClient.debug('No changes in %s: rds_qos_threshold_action is the same and is equal to %s!' % (rds_conf_file, out.rstrip('\n')) )

    return request.param


@pytest.fixture(scope="function", params=["256","2K", "256K", "1M", "2M"])
def data(request):
    data = {}
    
    if request.param == "256":
        data = { "data_size":"256", "queue_val":1}
    if request.param == "2K":
        data = { "data_size":"2K", "queue_val":1}
    if request.param == "256K":
        data = { "data_size":"256K", "queue_val":2}
    if request.param == "1M":
        data = { "data_size":"1M", "queue_val":2}
    if request.param == "2M":
        data = { "data_size":"2M", "queue_val":2}

    return data

def pytest_generate_tests(metafunc):
    loggerClient.debug('Generate %s, %s' % (metafunc.function.__name__, metafunc.fixturenames))
    if 'data' in metafunc.fixturenames:
        loggerClient.debug('Generating data!')
#        This function magically solves the problem with sorting 
#        of the input fixture parameters which shall be grouped by configured_threshold value
#        we do not need to set actual argvalues and call parametrize() here at all   
#        argvalues = ["256","2K", "256K", "1M", "2M"]
#        metafunc.parametrize('data', argvalues, indirect=True) 

# def test_default_rds_qos_threshold_values():

#     """
#      Only on clean system.
#      Need to check here is the system is just installed 
#     """
#     pytest.skip("Only on clean system")

#     """
#      Verify for the default value of rds_qos_threshold and rds_qos_threshold_action parameters 
#      using cat /sys/module/rds/parameters/rds_qos_threshold and cat /sys/module/rds/parameters/rds_qos_threshold_action. 
#      Default values will be null and 0 respectively.    
#     """

#     out, err = run('cat /sys/module/rds/parameters/rds_qos_threshold', shell=True)
#     assert out == '(null)' ,  "Unexpected result. The default value of rds_qos_threshold shall be null!"
#     out, err = run('cat /sys/module/rds/parameters/rds_qos_threshold_action', shell=True)
#     assert int(out) == 0 ,  "Unexpected result. The default value of rds_qos_threshold_action shall be null!"


def test_rds_stress(configured_threshold, data):

    rds_qos_threshold_action = configured_threshold
    data_size = data["data_size"]
    queue_val = data["queue_val"]
    
    loggerClient.debug('rds_qos_threshold_action == %s' % rds_qos_threshold_action)
    loggerClient.debug('Port: %s' % rds_server_port)
    loggerClient.debug('Size of Data packet: %s' % data_size)
    loggerClient.debug('Queue value: %s' % queue_val)
    
    """
     Test step 1
       get values of RDS parameters on both server and client hosts
       before rds-stress command is executed
    """
    _fetch_parameter("NextTX",queue_val,'client')
    _fetch_parameter("NextRX",queue_val,'client')

    _fetch_parameter("NextTX",queue_val,'server' )
    _fetch_parameter("NextRX",queue_val,'server')

    if (rds_qos_threshold_action == 2) or (rds_qos_threshold_action == 3): # statistics about threshold shall be gathered
        _fetch_parameter("qos_threshold_exceeded",queue_val,'client')

    """
     Test step 2
        Start rds-stress as a server
    """
    rds_server_proc = subprocess.Popen('ssh -l root %s \'%s -p %s 2>&1\'' % (ofed_server_ip['eth0'].ip, rds_stress, rds_server_port), 
                                                #bufsize=0,
                                                stdout=subprocess.PIPE, 
                                                stderr=subprocess.PIPE, 
                                                shell=True)     
    rds_server_proc.poll()
    if rds_server_proc.returncode != None:
        pytest.fail("Failed to start RDS server")
    else:
        # Looking for "waiting for incoming connection on 0.0.0.0:50??" output
        loggerServer.debug('rds-stress command:')
        loggerServer.debug('%s' % rds_server_proc.stdout.readline().rstrip('\n') ) 

    """
     Test step 2
     execute rds-stress utility
    """        
    out, err = run("%s -s %s -p %s -D %s -Q %s -T 10" % (rds_stress,ofed_server_ip[ib_device].ip,rds_server_port,data_size, queue_val), shell=True)
    

    """
     Test step 3
     get logs of rds-stress server
    """        

    rds_server_proc.poll()
    if rds_server_proc.returncode == None:
        rds_server_proc.kill()

    server_out, server_err = rds_server_proc.communicate()
    if server_out != "":
        log("Server rds-stress command output:", server_out, writer=lambda s: loggerServer.debug(s))
    if server_err != "":
        log("Server rds-stress command errors:", server_err, writer=lambda s: loggerServer.error(s))


    """
     Test step 4
       get values of RDS parameters on both server and client hosts
       afer rds-stress command is executed
    """
    _fetch_parameter("NextTX",queue_val,'client')
    _fetch_parameter("NextRX",queue_val,'client')

    _fetch_parameter("NextTX",queue_val,'server')
    _fetch_parameter("NextRX",queue_val,'server')

    if (rds_qos_threshold_action == 2) or (rds_qos_threshold_action == 3): # statistics about threshold shall be gathered
        _fetch_parameter("qos_threshold_exceeded",queue_val,'client')

    """
     Test results verification:
       Compare values of parameters gethered before and after rds-stress utility is executed
       depending on configured value of rds_qos_threshold_action parameter
    """    
    if data_size == "2M":  
        assertMessage([ err, server_err ] , "sendto() failed, errno: 22 (Invalid argument)")

    elif (rds_qos_threshold_action == 0) or (rds_qos_threshold_action == 2) or (data_size == "256") or (data_size == "256K"): 
        # ignore thresholds
        assert err == "" , "Warning! %s was executed with unxpected error output: %s" % (rds_stress, err)  
        
        assertValueIncreased("NextTX",'client')
        assertValueIncreased("NextRX",'client')

        assertValueIncreased("NextTX",'server')
        #assertValueIncreased("NextRX",'server')

        if (rds_qos_threshold_action == 2 ) and (data_size.count('256') == 0):
        # statistics about exceeded threshold shall be gathered
            assertValueIncreased("qos_threshold_exceeded",'client')

    elif (rds_qos_threshold_action == 1) or (rds_qos_threshold_action == 3): 
        # error if threshold is exceeded
        if (data_size == "2K"):  
            assertMessage([ err, server_err ], "sendto() failed, errno: 22 (Invalid argument)")

        if rds_qos_threshold_action == 3:
            assertValueIncreased("NextTX",'client')
            assertValueIncreased("NextRX",'client')
            assertValueIncreased("qos_threshold_exceeded",'client')
    else:
        pytest.fail("Shall never be here with any parameters: %s" % data)
   
