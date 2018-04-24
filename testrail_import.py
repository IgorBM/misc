# -*- coding: latin-1 -*-
import unittest
import csv
import argparse
import io
import re
from os.path import basename
import time
from testrail import *


class MyException(Exception):
    pass

class SuitetoTestRailImport():

        url = "https://???.testrail.com/"
        login = "???@???.com"
        passwd = "???"
        client = None

        # Input parameters
        # ID of Content project is 3
        project_id = 3
        expected_suite_id = ""
        infile = ""
        outfile = ""

        # Internal data structures
        tests = []
        suite = {}
        csv_sections = {}
        existing_sections = None
        existing_tests = None
        all_priorities = None
        all_types = None
        line_number = re.compile("^\d+\.\s")
        site_pattern = re.compile("https?\://[a-z]{2,3}\.ixl\.[a-z][0-9]{1,3}\:[0-9]{5}/")
        s954_pattern1 = re.compile("Target Environment\: https://[a-z]{2,3}.ixl.[a-z][0-9]{1,3}\:[0-9]{5}/")
        s954_subst1 = "Target Page: /"
        s954_pattern2 = re.compile("Comparison Environment\: https?\://[a-z]{2,3}\.ixl\.[a-z][0-9]{1,3}\:[0-9]{5}/.*")
        s954_subst2 = ""

        def __init__(self, project_name=None, expected_suite_id=None, credentials=None, file_name=None):
            print('Processing input parameters and Initializing data structures...')

            if project_name:
                print('Initializing API Client...')
                self.__class__.client = APIClient(self.url)
                if credentials and not credentials == ":":
                    login, passwd = credentials.split(':')
                    self.__class__.client.user = login
                    self.__class__.client.password = passwd
                else:
                    self.__class__.client.user = self.login
                    self.__class__.client.password = self.passwd

                print('Obtaining Project ID...')
                self.__class__.project_id = self.get_project_id(project_name)

            self.__class__.expected_suite_id = expected_suite_id
            self.__class__.infile = file_name
            file_parts = basename(file_name).split('.')
            self.__class__.outfile = file_parts[0]+"_processed."+file_parts[1]

        def process_section(self, test_id, name, desc, hierarchy):
            # Try to find Section ID by Test Case ID in existing TestRail cases
            section_id = self.get_section_id_by_test(test_id=test_id)
            if section_id:
                # Simply update Section
                self.update_section(section_id, name, desc)
            else:
                # Process Hierarchy and Create
                parent_id = None
                path = hierarchy.strip().split(' > ')
                for index, level_name in enumerate(path):
                    # check it is a last element
                    if index == len(path)-1:
                        tmp_desc = desc
                    else:
                        # Hope that order of rows in CSV file  will provide only existing sections in Hierarchy
                        # But if it's also a new Section - we need to create it with empty description
                        tmp_desc = ""
                    # Find Section ID by its Name and Depth among existing Test Rail Sections
                    section_id = self.get_section_id(level_name, index, parent_id)
                    if section_id:
                        # update if it is the last section in hierarchy
                        if index == len(path) - 1:
                            self.update_section(section_id, name, desc)
                        else:
                            parent_id = section_id
                    else:
                        new_section = self.add_section(level_name, tmp_desc, parent_id)
                        if new_section:
                            parent_id = new_section['id']
                            section_id = new_section['id']
                        else:
                            raise Exception("Unable to add a new Section")

            return section_id

        def normalize_csv(self):
            print("Making better CSV...")

            # ID,Title,Created By,Created On,Estimate,Forecast,Milestone,Preconditions,
            # Priority,References,Section,Section Depth,Section Description,Section Hierarchy,
            # Steps,Steps (Expected Result),Steps (Step),Suite,Suite ID,Type,Updated By,Updated On
            fieldnames = ['ID', 'Title', 'Preconditions', 'Priority', 'Section', 'Section Depth', 'Section Description',
                          'Section Hierarchy', 'Steps (Step)', 'Steps (Expected Result)', 'Suite', 'Suite ID', 'Type']
            to_remove = ['Updated On', 'Forecast', 'Milestone', 'Estimate', 'Updated By', 'Steps', 'Created By',
                         'Created On', 'References', 'Template', 'Tags']
            
            step_row = { key : "" for key in fieldnames }

            infile = io.open(self.infile, "r", encoding='utf-8-sig' )
            # next(infile, None)
            probe_header = infile.readline()

            # has_header = csv.Sniffer().has_header(infile.readline())
            if "sep=" not in probe_header:
                infile.seek(0)

            reader = csv.DictReader(infile)
            
            # headers = [s.encode("utf-8").strip('"') for s in infile.readline().rstrip('\n').split(',')]
            # print ("Headers %s" % headers)
     
            with io.open(self.outfile, "w", encoding='utf-8', newline='') as outfile:

                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()

                for row in reader:
                    
                    steps = []
                    expectations = []
                    #print (row)
                    for key in to_remove:
                        if key in row.keys():
                            del row[key]

                    row_keys = row.keys()

                    if row['Suite ID'] == 'S954':
                        tmp_precond = re.sub(self.s954_pattern1, self.s954_subst1, row['Section Description'])
                        row['Section Description'] = re.sub(self.s954_pattern2, self.s954_subst2, tmp_precond)

                    for k in ['Preconditions','Steps (Step)', 'Steps (Expected Result)', 'Section Description']:
                        if k in row_keys:
                            row[k] = re.sub(self.site_pattern,"/", row[k])

                    if 'Steps (Step)' in row_keys:
                        if row['Steps (Step)'] != "":
                            steps = row['Steps (Step)'].strip('\n')
                            # print("Unprocessed steps: ", steps)
                            # steps = [ x.rstrip('\n') for x in re.split('^\d+\.\s+', steps ,flags=re.MULTILINE) if x != '']
                            steps = [ x.rstrip('\n') for x in re.split('\n+(?=^\d+\.\s*)', steps ,flags=re.MULTILINE)]
                            # print ("Processed :", steps)
                    row['Steps (Step)'] = ""
                            
                    if 'Steps (Step)' in row_keys: 
                        if row['Steps (Expected Result)'] != "":
                            expectations = row['Steps (Expected Result)'].strip('\n')
                            # print("Unprocessed expectations: ", expectations)
                            # expectations = [ x.rstrip('\n') for x in re.split('^\d+\.\s+', expectations ,flags=re.MULTILINE) if x != '']
                            expectations = [ x.rstrip('\n') for x in re.split('\n+(?=^\d+\.\s*)', expectations ,flags=re.MULTILINE) if x != '']
                            # print ('Processed exp: ',expectations)
                    row['Steps (Expected Result)'] = ""

                    # write test row
                    writer.writerow(row)

                    # write steps-expectations separately on row below the test
                    for s,e in zip(steps, expectations):
                        step_row['Steps (Step)'] = s
                        step_row['Steps (Expected Result)'] = e
                        writer.writerow(step_row)
                        step_row['Steps (Step)'] = ""
                        step_row['Steps (Expected Result)'] = ""

                infile.close()

        def parse_normalized_csv(self):
            print("Parsing normalized CSV ...")
            # encoding = 'utf-8'
            encoding = 'latin-1'
            with io.open(self.infile, "r", encoding=encoding,  newline='') as f:
                reader = csv.DictReader(f)
                suite = {}
                sections = {}

                row = next(reader)
                if not ''.join(row.values()).strip():
                    row = next(reader)
                fieldnames = row.keys()
                while True:
                    try: 
                        # print('Row: ', row)
                        test = {}

                        # Process suite data, but add a suite only once
                        if not self.suite:
                            suite_id, suite_name = "", ""
                            if 'Suite ID' in fieldnames:
                                if row['Suite ID'] != self.expected_suite_id:
                                    raise Exception("Suite ID %s from %s file does not match with expected %s" % \
                                          (row['Suite ID'], self.infile, self.expected_suite_id))
                                else:
                                    suite_id = row['Suite ID'].lstrip('S')

                            if 'Suite' in fieldnames:
                                suite_name = row['Suite']
                            suite.update({'suite_id' : suite_id,
                                          'name': suite_name,
                                          'descriptions': ''})
                            self.__class__.suite.update(suite)

                        # Process test data
                        test['title'] = row['Title']

                        if 'ID' in fieldnames:
                            test_id = row['ID'].lstrip('C')
                            test['id'] = test_id
                        else:
                            test_id = 0

                        if 'Priority' in fieldnames:
                            test['priority_id'] = self.get_priority_id(row['Priority'])
                        else:
                            test['priority_id'] = 2

                        if 'Type' in fieldnames:
                            test['type_id'] = self.get_type_id(row['Type'])
                        else:
                            test['type_id'] = 1

                        if 'Preconditions' in fieldnames:
                            test['custom_preconds'] = row['Preconditions']

                        # Process section data
                        if 'Section Description' in fieldnames:
                            section_desc = row['Section Description']
                        else:
                            section_desc = ""
                        if 'Section Hierarchy' in fieldnames:
                            section_hierarchy = row['Section Hierarchy']
                        else:
                            section_hierarchy = ""
                        test['section_id'] = self.process_section(int(test_id), row['Section'], section_desc, section_hierarchy )

                        # Process test steps
                        custom_steps = []
                        if not row['Steps (Step)'] and not row['Steps (Expected Result)']:
                            # Assume the next is a "step-expectation" row
                            row = next(reader)
                            if not ''.join(row.values()).strip():
                                row = next(reader)
                            while row['Title'] == "":
                                step = re.sub(self.line_number, "", row['Steps (Step)'])
                                expected = re.sub(self.line_number, "", row['Steps (Expected Result)'])
                                custom_steps.append({'content': step, 'expected': expected})
                                row = next(reader)
                                if not ''.join(row.values()).strip():
                                    row = next(reader)

                            # print('Next row: ', row)
                            test['custom_steps_separated'] = custom_steps
                            # print ('Custom steps: ',test['custom_steps_separated'])
                        else:
                            # Introduced this section if "step-expectation" cells in a main test row contains data
                            test['custom_steps_separated'] = []
                            step = re.sub(self.line_number, "", row['Steps (Step)'])
                            expected = re.sub(self.line_number, "", row['Steps (Expected Result)'])
                            test['custom_steps_separated'].append({ 'content': step,'expected': expected})
                            row = next(reader)
                            if not ''.join(row.values()).strip():
                                row = next(reader)

                        self.__class__.tests.append(test)

                    except KeyError as err:
                        print('Error: Need to know about test %s. Please add this info into your file!' % err)
                        raise KeyError(err)
                    except csv.Error:
                        print("Error in CSV file %s" % self.outfile)
                    except StopIteration:
                        print("Iteration End")
                        test['custom_steps_separated'] = custom_steps
                        self.__class__.tests.append(test)
                        break

                #self.__class__.csv_sections = sections
                print('Collected tests: ',self.tests)
                #print('Collected sections: ',self.csv_sections)

        def parse_exported_csv(self):
            
            print ("Parsing exported CSV in original format...")
            with io.open(self.infile, "r", encoding='utf-8') as f:
                    # data = f.read()
                    # Omit the first line
                    # next(csvfile, None)
                     
                    # tail -n +2 $INFIL | whatever_script.py 
                    suite = {}
                    sections = {}
                    reader = csv.DictReader(f)
                    for row in reader:
                        test = {}
                        # print row
                        # print '\n'

                        # Process suite data
                        suite_id = row['Suite ID'].lstrip('S')                    
                        if suite_id not in suite.keys():
                            suite.update({'suite_id' : suite_id,
                                          'name' : row['Suite'],
                                          'descriptions': ''})
                        self.__class__.suite.update(suite)

                        # Process test data
                        test['id'] = row['ID'].lstrip('C')
                        test['title'] = row['Title']
                        test['custom_preconds'] = row['Preconditions']

                        if row['Steps (Step)'] != "":
                            steps = row['Steps (Step)'].strip('\n')
                            steps = [ x.rstrip('\n') for x in re.split('^\d+\.\s+', steps ,flags=re.MULTILINE) if x != ''] 
                            # print steps, '\n'

                            expectations = row['Steps (Expected Result)'].strip('\n')
                            expectations = [ x.rstrip('\n') for x in re.split('^\d+\.\s+', expectations ,flags=re.MULTILINE) if x != ''] 
                            # print expectations, '\n'

                            keys = ['content','expected']
                            custom_steps = []
                            for s,e in zip(steps,expectations):
                                    custom_steps.append(dict(zip(keys, [s,e])))
                                                        
                            test['custom_steps_separated'] = custom_steps
                            # print test['custom_steps_separated']

                        # Process section data
                        if row['Section'] not in sections.keys():
                            print ("Section has not been processed yet...")
                            section_id = self.get_section_id(row['Section'])
                            test['section_id'] = section_id
                            sections[row['Section']] = {'name': row['Section'],
                                                        'id': section_id,
                                                        'description': row['Section Description'],
                                                        'hierarchy': row['Section Hierarchy'] }
                        else:
                            print ("Already have info about this Section...")
                            test['section_id'] = sections.get(row['Section'])['id']

                        self.__class__.tests.append(test)

                    self.__class__.csv_sections = sections
                    print('Collected tests: ', self.tests)
                    print('Collected sections: ', self.sections)
                            
        def get_project_id(self, name):
            projects = self.client.send_get("get_projects")
            for p in projects:
                    if p['name'] == name:
                            return int(p['id'])
            print("Warning: unable to find a project: ", name)
            return None

        def fetch_all_testrail_sections(self):
            project_id = self.project_id
            suite_id = self.suite['suite_id']
            print ("Fetching Sections from TestRail...")
            result = self.client.send_get("get_sections/%s&suite_id=%s" % (project_id, suite_id))
            try:
                print("Error: ", result['error'])
            except (KeyError, TypeError):
                self.__class__.existing_sections = result


        def fetch_all_testrail_cases(self):
            project_id = self.project_id
            suite_id = self.suite['suite_id']
            print ("Fetching Existing Test Cases from TestRail...")
            result = self.client.send_get("get_cases/%s&suite_id=%s" % (project_id, suite_id))
            try:
                print("Error: ", result['error'])
            except (KeyError, TypeError):
                self.__class__.existing_tests = result

        def get_section_id_by_test(self, test_id):
            if test_id == 0:
                return None
            if self.existing_tests is None:
                print("Going to fetch info about All Test Cases...")
                self.fetch_all_testrail_cases()

            for tc in self.existing_tests:
                if tc['id'] == int(test_id):
                    return int(tc['section_id'])

            return None

        def get_section_id(self, name, depth, parent_id):
            first_time = False
            if self.existing_sections is None:
                first_time = True
                print("Going to fetch info about All Sections...")
                self.fetch_all_testrail_sections()

            for s in self.existing_sections:
                if s['name'] == name and s['depth'] == depth and s['parent_id'] == parent_id:
                    return int(s['id'])

            if not first_time:
                print("Going to refresh info about All Sections...")
                self.fetch_all_testrail_sections()

                for s in self.existing_sections:
                    if s['name'] == name and s['depth'] == depth and s['parent_id'] == parent_id:
                        return int(s['id'])

            return None

        def get_priority_id(self, name):
            if self.all_priorities is None:
                print("Going to fetch info about All Priorities...")
                all_priorities = self.client.send_get("get_priorities")
                # print(all_priorities)
                # TODO Verify if the result output is not an error here
                self.__class__.all_priorities = all_priorities
            else:
                # print("Info about All Priorities was already collected...")
                pass

            for s in self.all_priorities:
                if s['name'] == name:
                    return int(s['id'])

            return None

        def get_type_id(self, name):
            project_id = self.project_id
            suite_id = self.suite['suite_id']
            # print suite_id
            if self.all_types is None:
                print("Going to fetch info about All Test Types...")
                all_types = self.client.send_get("get_case_types")
                # print(all_types)
                # TODO Verify if the result output is not an error here
                self.__class__.all_types = all_types
            else:
                # print("Info about All Test Types was already collected...")
                pass

            for s in self.all_types:
                if s['name'] == name:
                    return int(s['id'])

            return None

        def add_cases(self):
            print ("Adding Test Cases...")
            # print ("Tests:", tests)
            for test in self.tests:
                # prepare a dict with ALL parameters to be updated
                params = {}
                # API recognizes the following  fields
                # title, template_id, type_id, priority_id, estimate, milestone_id,
                # refs, custom_preconds, custom_steps_separated
                allowed_fields = ['title', 'template_id', 'type_id', 'priority_id', 'estimate',
                                  'milestone_id', 'refs', 'custom_preconds', 'custom_steps_separated']
                # Excluding 'custom_steps' field because we work with 'custom_steps_separated'
                for key in test.keys():
                    if key == 'id':
                        continue
                    if key not in allowed_fields:
                        continue
                    params.update({key: test[key]})

                if test['section_id'] is not None:
                    # Do addition
                    result = self.client.send_post(
                        "add_case/%s" % test['section_id'],
                        params)
                    try:
                        print("Error: ", result['error'])
                    except (KeyError, TypeError):
                        # print(result)
                        pass
                else:
                    print("Please add a Section before adding the test \"%s\"" % test['title'])
                    pass

        def process_cases(self):
            result = {'error':'no creation no updating has been performed!'}
            operation = 'create'
            # print ("Tests:", tests)
            for test in self.tests:
                # prepare a dict with ALL parameters to be updated
                params = {}
                # API recognizes the following  fields
                # title, template_id, type_id, priority_id, estimate, milestone_id,
                # refs, custom_preconds, custom_steps_separated
                allowed_fields = ['title', 'template_id', 'type_id', 'priority_id', 'estimate',
                                  'milestone_id', 'refs', 'custom_preconds', 'custom_steps_separated']
                # Excluding 'custom_steps' field because we work with 'custom_steps_separated'
                for key in test.keys():
                    if key == 'id':
                        operation = 'update'
                        continue
                    if key not in allowed_fields:
                        continue
                    params.update({key: test[key]})

                if operation == 'update':
                    # Do update
                    print("Updating Test Case...%s with ID %s" % (test['title'], test['id']))
                    try:
                        result = self.client.send_post(
                            "update_case/%s" % test['id'],
                            params)
                    except APIError as e:
                        print("Exception: ", e)
                        if "Field :case_id is not a valid test case." in e.args[0]:
                            print("Adding Test Cases...%s" % test['title'])
                            result = self.client.send_post(
                                "add_case/%s" % test['section_id'],
                                params)
                        else:
                            time.sleep(5)
                            print("Re-trying to update Test Cases after a time-out...%s" % test['title'])
                            result = self.client.send_post(
                                "update_case/%s" % test['id'],
                                params)

                elif operation == 'create':
                    if test['section_id'] is not None:
                        # Do addition
                        print("Adding Test Cases...%s" % test['title'])
                        try:
                            result = self.client.send_post(
                                "add_case/%s" % test['section_id'],
                                params)
                        except APIError as e:
                            time.sleep(5)
                            result = self.client.send_post(
                                "add_case/%s" % test['section_id'],
                                params)
                    else:
                        print("Please add a Section before adding the test \"%s\"" % test['title'])
                        pass
                else:
                    print("Unable to decide what to do the the test \"%s\"" % test['title'])
                    pass

                try:
                    print("Error: ", result['error'])
                except (KeyError, TypeError):
                    print(result)
                    pass

        def add_section(self, name, desc, parent_id):
            # prepare a dict with ALL parameters
            project_id = self.project_id
            suite_id = self.suite['suite_id']
            params = { 'name': name, 'suite_id': suite_id, 'description': desc, 'parent_id': parent_id }
            try:
                result = self.client.send_post(
                    "/add_section/%s" % project_id,
                    params
                )
            except APIError as e:
                time.sleep(5)
                result = self.client.send_post(
                    "/add_section/%s" % project_id,
                    params
                )
            try:
                print("Error: ", result['error'])
                return None
            except (KeyError, TypeError):
                print(result)
                return result


        def update_section(self, section_id, name, desc):
            print ("Updating A Section...")
            # prepare a dict with ALL parameters to be updated
            params = {'description': desc, 'name': name}
            # Do update
            try:
                result = self.client.send_post(
                    "update_section/%s" % section_id,
                    params
                            )
            except APIError as e:
                time.sleep(5)
                result = self.client.send_post(
                    "update_section/%s" % section_id,
                    params
                            )
            try:
                print("Error: ", result['error'])
                # return None
            except (KeyError, TypeError):
                print(result)
                # return result

        def update_sections(self):
            print ("Updating Sections of the Test Suite...")
            # print ("Sections:", self.csv_sections)
            for name in self.csv_sections:
                # print name
                section = self.csv_sections[name]
                keys = section.keys();
                params = {}
                # prepare a dict with ALL parameters to be updated
                if 'description' in keys:
                    params.update({ 'description' : section['description'] })
                if 'name' in keys:
                    params.update({ 'name' : section['name'] })
                # Do update
                result = self.client.send_post(
                    "update_section/%s" % section['id'],
                    params
                            )
                print (result)

        def update_suite(self):
            print ("Updating Plan Suite...")

        def test_rail_import(self):
                # print "Importing to TestRail..."
                # self.parse_exported_csv()
                # self.normalize_csv()

                self.parse_normalized_csv()
                self.process_cases()
                # self.update_sections()
                
        def tearDown(self):
                pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Either parse a CSV file exported from TestRail and place each test "
                                                 "step on individual row or import a CSV file as a test suite")
    parser.add_argument("project", default="IXL Content", help="Name of IXL project in TestRail")
    parser.add_argument("suite_id", default="S777", help="ID of the TestRail's Suite to be imported")
    parser.add_argument("credentials", help="Credentials for logging into TestRail")
    parser.add_argument("file_name", help="Name of CSV file to be processed")
    args = parser.parse_args()

    print("Project: ", args.project)
    print("Suite ID: ", args.suite_id)
    print("Credentials: ", args.credentials)
    print("CSV file: ", args.file_name, flush=True)

    if args.project in ['Content', 'Product']:
        # Parse normalized file and do import
        ixl = SuitetoTestRailImport(args.project,args.suite_id, args.credentials, args.file_name)
        ixl.parse_normalized_csv()
        ixl.process_cases()
    elif args.project == 'Normalize':
        # Normalize a CSV file exported from TestRail
        ixl = SuitetoTestRailImport(file_name=args.file_name)
        ixl.normalize_csv()
    else:
        raise Exception('Unknown project %s' % args.project)
