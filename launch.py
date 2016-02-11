import unittest
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC

class LaunchMySession(unittest.TestCase):

	SessionSetup = False
	driver = None
	launch_page = "url" 

	def setUp(self):
		if not self.SessionSetup:
			print "Initializing testing environment"

			#profile = webdriver.FirefoxProfile()
			#profile.set_preference('network.http.phishy-userpass-length', 255)
			#self.driver = webdriver.Firefox(firefox_profile=profile)
			self.driver = webdriver.Firefox()

			# remember that it was setup already
			self.__class__.SessionSetup = True

	def test_login(self):
		driver = self.driver
		driver.get(self.launch_page)

		username = driver.find_element_by_id("os_username")
		password = driver.find_element_by_id("os_password")
		submit   = driver.find_element_by_id("loginButton")		
		
		# Input text in username and password inputboxes
		username.send_keys("user")
		password.send_keys("password")
 
		# Click on the submit button
		submit.click()
 		
 		# Create wait obj with a 5 sec timeout, and default 0.5 poll frequency
		wait = WebDriverWait(driver,5)

		# Test that login was successful by checking if the URL in the browser changed
		try:
			self.page_loaded = wait.until(EC.title_contains("Launch"))
		except TimeoutException:
			self.fail( "Loading timeout expired" )

		self.__class__.driver = driver


	def test_launch(self):
		driver = self.driver

		self.assertIn("Launch", driver.title)

		driver.find_element_by_xpath("//select[@id='lab']/option[@value='lab1']").click()
		driver.find_element_by_xpath("//select[@name='resultdb']/option[@value='test']").click()
		driver.find_element_by_xpath("//select[@name='repository']/option[@value='trunk']").click()
		driver.find_element_by_xpath("//select[@name='project']/option[@value='Proj']").click()
		driver.find_element_by_xpath("//select[@name='milestone']/option[@value='Milest']").click()
		driver.find_element_by_xpath("//select[@name='suite']/option[@value='MySuite']").click()
		driver.find_element_by_xpath("//select[@name='config']/option[@value='MyConf']").click()

		driver.find_element_by_xpath("//input[@id='launch_button']").click()

		# elem = driver.find_element_by_id("build")								
		# all_options = elem.find_elements_by_tag_name("option")
		# for option in all_options:
		# 	print("Value is: %s" % option.get_attribute("value"))


	def tearDown(self):
		pass
		#driver = self.driver
		#driver.close()

if __name__ == "__main__":
	unittest.main()		
