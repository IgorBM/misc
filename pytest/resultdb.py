#
# This is Python implementation of ResultDB report generator
#
# See also
#

import os, datetime, time
from xml.dom.minidom import Document

class LocalTZ(datetime.tzinfo):
    _unixEpochOrdinal = datetime.datetime.utcfromtimestamp(0).toordinal()

    def dst(self, dt):
        return datetime.timedelta(0)

    def utcoffset(self, dt):
        t = (dt.toordinal() - self._unixEpochOrdinal)*86400 + dt.hour*3600 + dt.minute*60 + dt.second + time.timezone
        utc = datetime.datetime(*time.gmtime(t)[:6])
        local = datetime.datetime(*time.localtime(t)[:6])
        return local - utc

def get_timestamp():
    return datetime.datetime.now(LocalTZ())
    
def timestamp_to_str(ts):
    timestamp = ts.strftime('%Y-%m-%dT%H:%M:%S%z')
    timestamp = timestamp[:22] + ':' + timestamp[22:]
    return timestamp 

def timedelta_to_str(td):
    h, rem = divmod(td.seconds, 3600)
    m, s = divmod(rem, 60)
    return '%d %02d:%02d:%02d.%06d' % (td.days, h, m, s, td.microseconds)

UNDEFINED = object()

TREND_SMALLER_IS_BETTER = 'smaller is better'
TREND_BIGGER_IS_BETTER  = 'bigger is better'  

def get_exported(name, default=UNDEFINED):
    name = os.environ.get('EXPORT_TEMPLATE', '%s') % name
    value = os.environ.get(name, default)
    if value == UNDEFINED:
        raise Exception('Undefined %s' % name)
    return value

class ResultDbReport(dict):
    
    def __init__(self, type=None):
        # Save current working directory since test can change it
        self.cwd = os.getcwd()
        
        # TODO Remove when old format will not be supported
        target_competitor = get_exported('TARGET_COMPETITOR', 'false').lower()
        if target_competitor == 'yes':
            target_competitor = 'true'
        elif target_competitor == 'no':
            target_competitor = 'false'
            
        self.update({
            '@type' : type,
            'timestamp'      : get_timestamp(),
            'owner' : {
                'email'      : get_exported('EMAIL_OWNER')
            },
            'log'            : get_exported('LOG_BASE'),
            'project'        : get_exported('PROJECT'),
            'milestone'      : get_exported('MILESTONE'),
            'suite' : {
                'name'       : get_exported('SUITE'),
                'version'    : get_exported('SUITE_VERSION'),
            },
            'target' : {
                'version'    : get_exported('TARGET'),
                'competitor' : target_competitor,
            },
            'config' : {
                'name'       : get_exported('CONFIG'),
                'property_list' : [],
            },
            'details_list' : [],
            'test_list' : [],
        })
        
    def xml(self):    
        return self._dict_to_xml(dict(report=dict(self))).toprettyxml(' ')
    
    def save(self, path=None):
        
        # Convert timestamp/timedelta to string format
        
        if 'timestamp' in self and isinstance(self['timestamp'], datetime.datetime):
            self['timestamp'] = timestamp_to_str(self['timestamp'])
        
        for test in self['test_list']:
            if 'timestamp' in test and isinstance(test['timestamp'], datetime.datetime):
                test['timestamp'] = timestamp_to_str(test['timestamp'])
            if 'duration' in test and isinstance(test['duration'], datetime.timedelta):
                test['duration'] = timedelta_to_str(test['duration'])
        
        self.filename = os.path.join(path or self.cwd, ('rdb-%s-%s-%s.xml' % (self['milestone'], self['suite']['name'], self['config']['name'])).replace(' ', '_')) 
        f = open(self.filename, 'w')
        try:
            f.write(self.xml())
        finally:
            f.close()
        
    # Dictionary to XML converter
    def _dict_to_xml(self, data, doc=None, parent=None):
        if not doc:
            doc = Document()
            parent = doc
        if type(data) == type([]):
            for item in data:
                node = doc.createElement('item')
                self._dict_to_xml(item, doc, parent.appendChild(node))
        elif type(data) == type({}):
            for key in sorted(data.keys()):
                if data[key]:
                    if key.startswith('@'):
                        parent.setAttribute(key[1:], data[key])
                    else:
                        node = doc.createElement(key)
                        self._dict_to_xml(data[key], doc, parent.appendChild(node))
        else:
            node = doc.createTextNode(str(data))
            parent.appendChild(node)
    
        return parent

class PyTestPlugin(object):
    '''
        This is PyTest plugin to generate ResultDB report automatically.
        Add conftest.py file to the root folder of tests, e.g.
             
        import resultdb
        
        def pytest_configure(config):
            config.pluginmanager.register(resultdb.PyTestPlugin(), 'resultdb')
            report = config.pluginmanager.getplugin("resultdb").report
            
            import multiprocessing
        
            report['config']['property_list'].append({
                'type'  : 'important',
                'key'   : 'CPU count',
                'value' : multiprocessing.cpu_count()
            })
        
            report['details_list'].append({
                'key'   : 'CPU count',
                'value' : multiprocessing.cpu_count()
            })
    '''
    
    def __init__(self, filename=None):
        self.report = ResultDbReport(type='auto')
    
    def get_testname(self, report):
        names = report.nodeid.split("::")
        names = [x.replace(".py", "") for x in names if x != '()']
        names[0] = names[0].replace("/", '.')
        classnames = names[:-1]
        return ".".join(classnames) + '.' + names[-1]
    
    # pytest hook
    def pytest_runtest_logreport(self, report):
        status = None
        if report.passed:
            if report.when == "call": # ignore setup/teardown
                status = 'passed'
        elif report.failed:
            if report.when != "call":
                status = 'failed' # need error
            else:
                status = 'failed'
        elif report.skipped:
                status = 'skipped'
        if status:
            
            # report.longrepr contains full stacktrace while
            # short error message is enough for ResultDB report
            #
            # skipped test doesn't have reprcrash and report.longrepr
            # is tuple, e.g.
            # tuple: ('/usr/local/lib/python2.7/dist-packages/pytest-2.3.5-py2.7.egg/_pytest/skipping.py', 120, 'Skipped: my reason')
            message = None 
            if report.longrepr:
                if hasattr(report.longrepr, 'reprcrash'):
                    message = report.longrepr.reprcrash.message
                else:
                    message = report.longrepr[2][9:] 
                    
            self.report['test_list'].append({
                    'timestamp' : get_timestamp(),
                    'name'      : self.get_testname(report),
                    'status'    : status,
                    'message'   : message
            })
            
    # pytest hook
    def pytest_sessionfinish(self, session, exitstatus, __multicall__):
        self.report.save()

    # pytest hook
    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("-", "generated ResultDB XML report: %s" % (self.report.filename))

def usage_example():

    # Following env variables are being exported by test launcher automatically 
    # depends on build and test info of particular run
    # See actual list of variables on wiki
    #
    # IMPORTANT: Test script must not define or override these variables
    #
    os.environ.update({
        'LOG_BASE'          : 'http://???.???.117.???/results/results',
        'PROJECT'           : 'foo',
        'MILESTONE'         : 'bar',
        'SUITE'             : 'TestSuite',
        'SUITE_VERSION'     : '638',
        'TARGET'            : '3.8.13-3',
        'TARGET_COMPETITOR' : 'false',
        'CONFIG'            : 'Config1',
        'EMAIL_OWNER'       : 'foo.bar@email.com'
    })

    import multiprocessing

    report = ResultDbReport(type='performance')
    
    # Collect configuration info
    report['config']['property_list'].append({
        'type'  : 'important',
        'key'   : 'CPU count',
        'value' : multiprocessing.cpu_count()
    })

    report['log'] += '/test_results_folder'
    
    start = get_timestamp()
    time.sleep(0.123)
    
    # Collect test results
    report['test_list'].append({
            'timestamp' : start,
            'name'      : 'test1',
            'duration'  : get_timestamp() - start,
            'value'     : 838.99,
            'unit'      : 'transactions/second',
            'trend'     : TREND_BIGGER_IS_BETTER,
            'threshold' : 5
    })
    
    start = datetime.datetime(2009,2,10,14,00,00,tzinfo=LocalTZ())
    end   = datetime.datetime(2009,2,12,16,01,24,13,tzinfo=LocalTZ())
    
    report['test_list'].append({
            'timestamp' : start,
            'name'      : 'test2',
            'duration'  : end - start,
            'value'     : 23.4,
            'unit'      : 'second',
            'trend'     : TREND_SMALLER_IS_BETTER,
            'threshold' : 5
    })

    os.chdir('/tmp/')
    report.save()
    
    # Generate report
    print report.xml()
        
    ''' Output
        <?xml version="1.0" ?>
        <report type="performance">
         <config>
          <name>specjvm x86_64</name>
          <property_list>
           <item>
            <key>CPU count</key>
            <type>important</type>
            <value>8</value>
           </item>
          </property_list>
         </config>
         <log>test_results_folder</log>
         <milestone>foo3</milestone>
         <owner>
          <email>foo.bar@email.com</email>
         </owner>
         <project>foo</project>
         <suite>
          <name>SpecJVM</name>
          <version>638</version>
         </suite>
         <target>
          <competitor>false</competitor>
          <version>3.8.13-3</version>
         </target>
         <test_list>
          <item>
           <duration>0 00:00:00.123183</duration>
           <name>test1</name>
           <threshold>5</threshold>
           <timestamp>2014-01-21 17:28:53.846993+04:00</timestamp>
           <trend>bigger is better</trend>
           <unit>transactions/second</unit>
           <value>838.99</value>
          </item>
          <item>
           <duration>2 02:01:24.000013</duration>
           <name>test2</name>
           <threshold>5</threshold>
           <timestamp>2009-02-10 14:00:00+03:00</timestamp>
           <trend>smaller is better</trend>
           <unit>second</unit>
           <value>23.4</value>
          </item>
         </test_list>
         <timestamp>2014-01-21T17:28:53+04:00</timestamp>
        </report>
    '''

if __name__ == '__main__':
    usage_example()
