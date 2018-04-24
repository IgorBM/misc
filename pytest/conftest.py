#import resultdb
import os, logging, datetime
from ofed_utils import *
import multiprocessing

LOG_FILE_NAME = 'ofed_tests.log'

logging.basicConfig(filename=LOG_FILE_NAME,
                    filemode='w',
                    format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

def pytest_configure(config):

    setup_network()

    client_system_version = os_release()
    server_system_version = remote_os_release()

    '''
     Workaround for Autotest OLTF resultdb.py expected variables
    '''
    try:
        get_env('EMAIL_OWNER')
    except:
        os.environ['EMAIL_OWNER']       = "me@email.com"
        os.environ['LOG_BASE']          = "/home/tests/"
        os.environ['PROJECT']           = "foo"
        os.environ['MILESTONE']         = "foo4"
        os.environ['SUITE_VERSION']     = "1.0"
        os.environ['TARGET']            = "foo4"
        os.environ['TARGET_COMPETITOR'] = "False"
        os.environ['CONFIG']            = "test"
        os.environ['ISO_RELEASE']       = "OL6"
        os.environ['ITERATIONS']        = "1"

        # You must set SUITE variable manually in case of command line execution 
        # and distinguish between functional and performance tests for correct 
        # creation of resultdb.xml 

    import resultdb

    suite_name = get_env('SUITE', "functional")

    if 'functional' in suite_name:
        config.pluginmanager.register(resultdb.PyTestPlugin(), 'resultdb')

    # Properties to show in resultDB
    # CPU   Cache Size  
    #       MHz     
    #       Model
    #       Number
    # Common
    #       Arch    
    #       Manufacturer
    #       Meminfo
    #       Operation System
    #       Server Model
    # NIC   Driver  
    #       Model   
    #Storage
    #       Local Disk Model    
    #       Local Disk Size     
    #       Local Disk Vendor   

        ## For functional reports

        report = config.pluginmanager.getplugin("resultdb").report

        report['config']['property_list'].append({
            'type'  : 'unimportant',
            'key'   : 'CPU count',
            'value' : multiprocessing.cpu_count()
        })

        report['config']['property_list'].append({
            'type'  : 'important',
            'key'   : 'Arch',
            'value' : get_env('ARCH', 'x86_64')
        })

        report['config']['property_list'].append({
            'type'  : 'important',
            'key'   : 'Operation system',
            'value' : get_env('ISO_RELEASE', client_system_version )
        })


    else:  ## For performance reports
        report = resultdb.ResultDbReport(type='performance')

        #datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        report['timestamp'] = resultdb.timestamp_to_str(resultdb.get_timestamp())

        report['config']['name'] =  get_env('CONFIG', "test")

        report['config']['property_list'].append({
            'type'  : 'unimportant',
            'key'   : 'CPU count',
            'value' : multiprocessing.cpu_count()
        })

        report['config']['property_list'].append({
            'type'  : 'unimportant',
            'key'   : 'Arch',
            'value' : get_env('ARCH', 'x86_64')
        })

        report['config']['property_list'].append({
            'type'  : 'unimportant',
            'key'   : 'Operation system',
            'value' : get_env('ISO_RELEASE', client_system_version )
        })

    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'Operation system on server',
        'value' : server_system_version 
    })

    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'KERNEL',
        'value' : kernel_version()
    })

    
    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'KERNEL on server',
        'value' : kernel_version(host='remote')
    })

    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'RDMA version',
        'value' : rdma_version()
    })

    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'RDMA version on server',
        'value' : rdma_version(host='remote')
    })

    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'OFED info',
        'value' : ofed_info()
    })

    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'OFED info on server',
        'value' : remote_ofed_info()
    })

    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'rds-tools',
        'value' : rds_tools_version()
    })

    report['config']['property_list'].append({
        'type'  : 'unimportant',
        'key'   : 'rds-tools on server',
        'value' : rds_tools_version(host='remote')
    })


    jenkins_url = get_env('TRIGGERED_BY', "default")
    if jenkins_url != "default":
        report['config']['property_list'].append({
            'type'  : 'unimportant',
            'key'   : 'Jenkins Job',
            'value' : jenkins_url
        })

    keep_report(report)
    keep_os_version(client_system_version, server_system_version )

