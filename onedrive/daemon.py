#!/usr/bin/python

# Warning: Rely heavily on system time and if the timestamp is screwed there may be unwanted file deletions.

import sys
import os
import subprocess
import signal
import yaml
import threading, Queue, time
import re
import csv
import re
import StringIO
import gtk
import pynotify
from calendar import timegm
from dateutil import parser
from skydrive import api_v5

# Left click: show local repository
# Right click: show menu
class OneDrive_StatusIcon(gtk.StatusIcon):
	last_notification = None
	recent_changes = []
	PYNOTIFY_INITED = False
	_icon = None
	
	#@profile
	def __init__(self, api, rootPath):
		gtk.StatusIcon.__init__(self)
		
		self._rootPath = rootPath
		self._icon_pixbuf = gtk.gdk.pixbuf_new_from_file("./res/icon_256.png")
		self.set_from_pixbuf(self._icon_pixbuf)
		self.set_tooltip('onedrive-d')
		self.connect("activate", self.e_show_root)
		self.connect('popup-menu', self.e_click_icon)
		self.set_visible(True)
		
		self.menu = menu = gtk.Menu()
		
		item_open = gtk.MenuItem("Open OneDrive directory")
		item_open.connect("activate", self.e_show_root, "Open OneDrive directory")
		menu.append(item_open)
		
		self.item_recent = item_recent = gtk.MenuItem("Recent changes")
		item_recent_sub = gtk.Menu()
		item_recent_sub_all = gtk.MenuItem("All changes")
		item_recent_sub_all.connect("activate", self.e_show_monitor, None)
		item_recent_sub.append(item_recent_sub_all)
		item_recent_sub.append(gtk.SeparatorMenuItem())
		item_recent.set_submenu(item_recent_sub)
		menu.append(item_recent)
		
		menu.append(gtk.SeparatorMenuItem())
		
		self.item_quota = item_quota = gtk.MenuItem("Loading quota...");
		item_quota.connect("activate", self.e_update_quota, None)
		menu.append(item_quota)
		
		item_web = gtk.MenuItem("Visit OneDrive.com")
		item_web.connect("activate", self.e_show_web, None)
		menu.append(item_web)
		
		menu.append(gtk.SeparatorMenuItem())
		
		item_settings = gtk.MenuItem("Settings")
		item_settings.connect("activate", self.e_show_settings, None)
		menu.append(item_settings)
		
		item_test = gtk.MenuItem("test item")
		item_test.connect("activate", self.e_show_notification, None)
		menu.append(item_test)
		
		item_quit = gtk.MenuItem("Exit")
		item_quit.connect("activate", self.quit, "file.quit")
		menu.append(item_quit)
		
		menu.show_all()
		self.e_update_quota()
	
	#@profile
	def e_show_root(self, widget, event=None):
		subprocess.check_call(['gnome-open', self._rootPath, ''])
	
	#@profile
	def e_show_settings(self, widget, event=None):
		# OneDrive_SettingsWindow(self._icon_pixbuf)
		pass
	
	def e_show_monitor(self, widget, event=None):
		pass
	
	#@profile
	def e_click_icon(self, status, button, time):
		self.menu.popup(None, None, None, button, time)
	
	#@profile
	def e_show_web(self, widget=None, event=None):
		from webbrowser import open_new
		open_new("https://onedrive.com")
	
	#@profile
	def e_update_quota(self, widget=None, event=None):
		quota = api.get_quota()
		usedPercentage = float(quota[0]) / quota[1] * 100
		totalSize = "%.2fGiB" % (float(quota[1]) / 1073741824)
		self.item_quota.set_label("%.1f%% of %s Free" % (usedPercentage, totalSize))
		self.item_quota.set_sensitive(False)
	
	#@profile
	def e_show_notification(self, widget=None, event=None):
		self.add_notification("Title", "This is a test message!")
	
	#@profile
	def add_notification(self, title, text, icon = "notification-message-im", timeout = 2000):
		if not self.PYNOTIFY_INITED and not pynotify.init ("icon-summary-body"):
			return
		self.last_notification = pynotify.Notification(title, text, icon)
		self.last_notification.set_timeout(timeout)
		self.last_notification.show()
	
	def add_recent_change(self, path):
		submenu = self.item_recent.get_submenu()
		if submenu == None:
			pass
		pass
	
	def run(self):
		gtk.main()
	
	def quit(self, widget, event=None):
		gtk.main_quit()


# Task class models a generic task to be performed by a TaskWorker
# Tasks are put in the thread-safe Queue object
class Task():
	def __init__(self, type, p1, p2, timeStamp = None):
		self.type = type
		self.p1 = p1 # mostly used as a local path
		self.p2 = p2 # mostly used as a remote path
		if timeStamp!= None:
			self.timeStamp = timeStamp	# time, etc.
	
	def debug(self):
		return "Task(" + self.type + ", " + self.p1 + ", " + self.p2 + ")"
	
# TaskWorker objects consumes the tasks in taskQueue
# sleep when in idle
class TaskWorker(threading.Thread):
	WORKER_SLEEP_INTERVAL = 3 # in seconds
	
	def __init__(self):
		threading.Thread.__init__(self)
		self.daemon = True
		print self.getName() + " (worker): initiated"
	
	def getArgs(self, t):
		return {
			#"recent": [],
			#"info": [],
			#"info_set": [],
			"mv": ["mv", t.p1, t.p2],
			#"link": [],
			#"ls": [],
			"mkdir": ["mkdir", t.p2],	# mkdir path NOT RECURSIVE!
			"get": ["get", t.p2, t.p1],	# get remote_file local_path
			"put": ["put", t.p1, t.p2],	# put local_file remote_dir
			"cp": ["cp", t.p1, t.p2],	# cp file folder
			"rm": ["rm", t.p2]
		}[t.type]
	
	def consume(self, t):
		args = self.getArgs(t)
		subp = subprocess.Popen(['skydrive-cli'] + args, stdout=subprocess.PIPE)
		ret = subp.communicate()
		if t.type == "get":
			old_mtime = os.stat(t.p1).st_mtime
			new_mtime = timegm(parser.parse(t.timeStamp).utctimetuple())
			os.utime(t.p1, (new_mtime, new_mtime))
			new_old_mtime = os.stat(t.p1).st_mtime
			print self.getName() + ": " + t.p1 + " Old_mtime is " + str(old_mtime) + " and new_mtime is " + str(new_mtime) + " and is changed to " + str(new_old_mtime)
		if ret[0] != None and ret[0] != "":
			print "subprocess stdout: " + ret[0]
		if ret[1] != None and ret[0] != "":
			print "subprocess stderr: " + ret[1]
		print self.getName() + ": executed task: " + t.debug()
		
		del t
	
	def run(self):
		while True:
			if stopEvent.is_set():
				break
			elif taskQueue.empty():
				time.sleep(self.WORKER_SLEEP_INTERVAL)
			else:
				task = taskQueue.get()
				self.consume(task)
				taskQueue.task_done()

# DirScanner represents either a file entry or a dir entry in the OneDrive repository
# it uses a single thread to process a directory entry
class DirScanner(threading.Thread):
	_raw_log = []
	_ent_list = []
	_remotePath = ""
	_localPath = ""
	
	def __init__(self, localPath, remotePath):
		threading.Thread.__init__(self)
		self.daemon = True
		scanner_threads_lock.acquire()
		scanner_threads.append(self)
		scanner_threads_lock.release()
		self._localPath = localPath
		self._remotePath = remotePath
		print self.getName() + ": Start scanning dir " + remotePath + " (locally at \"" + localPath + "\")"
		self.ls()
	
	def ls(self):
		sema.acquire()
		#subp = subprocess.Popen(['skydrive-cli', 'ls', '--objects', self._remotePath], stdout=subprocess.PIPE)
		#log = subp.communicate()[0]
		try:
			self._raw_log = list(api.listdir(api.resolve_path(self._remotePath)))
		except api_v5.DoesNotExists as e:
			print "Remote path \"" + self._remotePath + "\" does not exist.\n({0}): {1}".format(e.errno, e.strerror)
		except api_v5.AuthenticationError as e:
			print "Authentication failed.\n({0}): {1}".format(e.errno, e.strerror)
		except (api_v5.SkyDriveInteractionError, api_v5.ProtocolError) as e:
			print "OneDrive API Procotol error.\n({0}): {1}".format(e.errno, e.strerror)
		sema.release()
		#if log.strip() != "":
			#self._raw_log = yaml.safe_load(log)
	
	def run(self):
		self.merge()
	
	# list the current dirs and files in the local repo, and in merge() upload / delete entries accordingly
	def pre_merge(self):
		# if remote repo has a dir that does not exist locally
		# make it and start merging
		if not os.path.exists(self._localPath):
			try:
				os.mkdir(self._localPath)
			except OSError as exc: 
					if exc.errno == errno.EEXIST and os.path.isdir(self._localPath):
						pass
		else:
			# if the local path exists, record what is in the local path
			self._ent_list = os.listdir(self._localPath)
			# check case sensitivity?
	
	# recursively merge the remote files and dirs into local repo
	def merge(self):
		self.pre_merge()
		
		if self._raw_log != None and self._raw_log != []:
			for entry in self._raw_log:
				if entry["name"] == None or "exclude" in CONF and re.match(CONF["exclude"], entry["name"]):
					continue
				if os.path.exists(self._localPath + "/" + entry["name"]):
					print self.getName() + ": Oops, " + self._localPath + "/" + entry["name"] + " exists."
					# do some merge
					self.checkout(entry, True)
					# after sync-ing
					del self._ent_list[self._ent_list.index(entry["name"])] # remove the ent from untouched list
				else:
					print self.getName() + ": Wow, " + self._localPath + "/" + entry["name"] + " does not exist."
					self.checkout(entry, False)
		
		self.post_merge()
	
	# checkout one entry, either a dir or a file, from the log
	def checkout(self, entry, isExistent = False):
		if entry["type"] == "file" or entry["type"] == "photo" or entry["type"] == "audio" or entry["type"] == "video":
			if isExistent:
				# assert for now
				assert os.path.isfile(self._localPath + "/" + entry["name"])
				local_mtime = os.stat(self._localPath + "/" + entry["name"]).st_mtime
				remote_mtime = timegm(parser.parse(entry["client_updated_time"]).utctimetuple())
				if local_mtime == remote_mtime:
					print self.getName() + ": " + self._localPath + "/" + entry["name"] + " wasn't changed. Skip it."
					return
				elif local_mtime > remote_mtime:
					print self.getName() + ": Local file \"" + self._localPath + "/" + entry["name"] + "\" is newer. Upload it..."
					taskQueue.put(Task("get", self._localPath + "/" + entry["name"] + "_remote_older", self._remotePath + "/" + entry["name"], entry["client_updated_time"]))
					# taskQueue.put(Task("put", self._localPath + "/" + entry["name"], self._remotePath))
				else:
					print self.getName() + ": Local file \"" + self._localPath + "/" + entry["name"] + "\" is older. Download it..."
					os.rename(self._localPath + "/" + entry["name"], self._localPath + "/" + entry["name"] + "_local_older")
					taskQueue.put(Task("get", self._localPath + "/" + entry["name"] + "", self._remotePath + "/" + entry["name"], entry["client_updated_time"]))
			else:
				# if not existent, get the file to local repo
				taskQueue.put(Task("get", self._localPath + "/" + entry["name"], self._remotePath + "/" + entry["name"], entry["client_updated_time"]))
		else:
			# print self.getName() + ": scanning dir " + self._localPath + "/" + entry["name"]
			DirScanner(self._localPath + "/" + entry["name"], self._remotePath + "/" + entry["name"]).start()
	
	# process untouched files during merge
	def post_merge(self):
		# there is untouched item in current dir
		if self._ent_list != []:
			print self.getName() + ": The following items are untouched yet:\n" + str(self._ent_list)
			
			for entry in self._ent_list:
				# assume to upload all of them
				# if it is a file
				if "exclude" in CONF and re.match(CONF["exclude"], entry):
					print self.getName() + ": " + entry + " is a pattern that is excluded."
				elif os.path.isfile(self._localPath + "/" + entry):
					taskQueue.put(Task("put", self._localPath + "/" + entry, self._remotePath))
				else:
					# if not, then it is a dir
					taskQueue.put(Task("mkdir", "", self._remotePath + "/" + entry))
					# print self.getName() + ": for now skip the untouched dir \"" + self._localPath + "/" + entry + "\""
		
		print self.getName() + ": done."
		# new logs should get from recent list
	
	# print the internal storage
	def debug(self):
		print "localPath: " + self._localPath + ""
		print "remotePath: " + self._remotePath + ""
		print self._raw_log
		print "\n"
		print self._ent_list
		print "\n"

# LocalMonitor runs inotifywait component and parses the log
# when an event is issued, parse it and add work to the task queue.
class LocalMonitor(threading.Thread):
	MONITOR_SLEEP_INTERVAL = 2 # in seconds
	EVENT_ON_HOLD = None
	
	def __init__(self):
		threading.Thread.__init__(self)
		self.rootPath = CONF["rootPath"]
	
	def handle(self, logItem):
		print "local_mon: received a task: " + str(logItem)
		dir = logItem[0]
		event = logItem[1]
		object = logItem[2]
		
		if "MOVED_TO" in event:
			taskQueue.put(Task("put", dir + object, dir.replace(self.rootPath, "")))
		elif "MOVED_FROM" in event:
			taskQueue.put(Task("rm", "", dir.replace(self.rootPath, "") + object))
		elif "DELETE" in event:
			taskQueue.put(Task("rm", "", dir.replace(self.rootPath, "") + object))
		elif "CLOSE_WRITE" in event:
			taskQueue.put(Task("put", dir + object, dir.replace(self.rootPath, "")))
		
	def run(self):
		if "exclude" in CONF:
			exclude_args = ["--exclude", CONF["exclude"]]
		else:
			exclude_args = []
		subp = subprocess.Popen(['inotifywait', '-e', 'unmount,close_write,delete,move', '-cmr', self.rootPath] + exclude_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		while True:
			# I think stdout buffer is fine for now
			if stopEvent.is_set():
				subp.terminate()
				break
			line = subp.stdout.readline()
			if line == "":
				if self.EVENT_ON_HOLD != None:
					self.handle(self.EVENT_ON_HOLD)
				time.sleep(self.MONITOR_SLEEP_INTERVAL)
			elif line[0] == "/":
				line = line.rstrip()
				csv_entry = csv.reader(StringIO.StringIO(line))
				for x in csv_entry:
					self.handle(x)
			else:
				print "Local_mon: >>>" + line
		
# RemoteMonitor periodically fetches the most recent changes from OneDrive remote repo
# if there are unlocalized changes, generate the tasks
class RemoteMonitor(threading.Thread):
	MONITOR_SLEEP_INTERVAL = 2 # in seconds
	
	def __init__(self, rootPath):
		threading.Thread.__init__(self)
	
	def run(self):
		pass

class IndicatorThread(threading.Thread):
		
	def __init__(self):
		threading.Thread.__init__(self)
		
	def run(self):
		ui.OneDrive_StatusIcon(api, CONF["rootPath"]).run()

def gracefulExit(signal, frame):
	print 'main: got signal ' + str(signal) + '!'
	stopEvent.set()
	for t in scanner_threads:
		t.join()
	for w in worker_threads:
		w.join()
	local_mon.join()
	sys.exit(0)

signal.signal(signal.SIGINT, gracefulExit)

CONF_PATH = "~/.onedrive"
NUM_OF_WORKERS = 2
NUM_OF_SCANNERS = 4

f = open(os.path.expanduser(CONF_PATH + "/user.conf"), "r")
CONF = yaml.safe_load(f)
f.close()

api = api_v5.PersistentSkyDriveAPI.from_conf("~/.lcrc")
try:
	quota = api.get_quota()
except api_v5.AuthenticationError as e:
	print "Authentication failed.\n({0}): {1}".format(e.errno, e.strerror)
	sys.exit(1)
except (api_v5.SkyDriveInteractionError, api_v5.ProtocolError) as e:
	print "OneDrive API Procotol error.\n({0}): {1}".format(e.errno, e.strerror)
	sys.exit(1)

IndicatorThread().start()
print quota
sys.exit(0)

scanner_threads = []
scanner_threads_lock = threading.Lock()
sema = threading.BoundedSemaphore(value = NUM_OF_SCANNERS)

taskQueue = Queue.Queue()

worker_threads = []
stopEvent = threading.Event()

for i in range(NUM_OF_WORKERS):
	w = TaskWorker()
	worker_threads.append(w)
	w.start()



DirScanner(CONF["rootPath"], "").start()

for t in scanner_threads:
	t.join()
	del t

taskQueue.join()


print "main: all done."

# Main thread then should create monitor and let workers continually consume the queue

print "main: create monitor"

#ui.TrayIcon(CONF["rootPath"])
#gtk.main()

local_mon = LocalMonitor()
local_mon.start()

signal.pause()

# remote_mon = RemoteMonitor()
# remote_mon.start()
