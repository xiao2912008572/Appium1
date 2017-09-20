#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os,threading,traceback
import random
import re
import subprocess
import sys
import time


class ADB(object):

    re_apk_package_name = re.compile(r"^package:\s+name='([a-zA-Z0-9_\.]*)'.*")
    re_apk_version_code = re.compile(r"^package:.*?versionCode='(\d*)'\s+.*")
    re_apk_version_name = re.compile(r"^package:.*?versionName='([0-9\.]*)'.*")
    re_apk_sdk_version = re.compile(r"^sdkVersion:\s*'(\d*)'.*$", 8)
    re_apk_launchable_activity = re.compile(r"^launchable\-activity:\s*name='([a-zA-Z0-9\.]*)'.*$", 8)
    re_apk_apk_label = re.compile(r"^launchable\-activity:.*?label='(.*?)'.*$", 8)
    re_uid = re.compile(r'userId=(\d+).*')
    re_focused_app_window_token = re.compile(r'[a-zA-Z0-9\.]+/([a-zA-Z0-9\.]+)')
    re_device_properties = re.compile(r"^\[(.+)\]:.?\[(.*)\]$")

    def __init__(self, device=None):
        self.devices = self.list_devices()
        if self.devices and self.devices[0].startswith("* daemon started"):
            self.devices = self.list_devices()

        if not self.devices:
            raise ADBNoDeviceFoundException("No device attached.")

        if device is None:
            self.device = self.devices[0]
        elif device in self.devices:
            self.device = device
        else:
            raise ADBNoDeviceFoundException("Device %s not found." % device)

        self.android_version = self._get_android_version()

    @staticmethod
    def _exec(cmd):
        version = float("%s.%s" % sys.version_info[0:2])
        print cmd
        if version >= 2.7:
            #print cmd
            return subprocess.check_output(cmd)
        else:
            return subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]

    def _adb_shell(self, *args):
        """Execute adb shell command."""        
        cmd = ['adb', '-s', self.device, 'shell']
        cmd.extend(args)
        #print cmd
        return self._exec(cmd).strip()

    def _ps(self, package_name):
        """This private method helps get pid of running app."""
        cmd = ['adb', '-s', self.device, 'shell', 'ps | grep %s$' % package_name]
        output = self._exec(cmd).strip()
        if output:
            fields = [x for x in output.split(' ') if x]
            headers = ['user', 'pid', "ppid", 'vsize', 'rss', 'wchan', 'pc', 'stat', 'name']
            return dict(zip(headers, fields))
        return {}

    def _get_uptime_of_system_and_idle(self):
        """Return a list object composed of two elements.

        The first one is uptime of the system (seconds), the second one is the amount
        of time spent in idle process (seconds).
        """
        cmd = ['adb', '-s', self.device, 'shell', 'cat /proc/uptime']
        output = self._exec(cmd).strip()
        if output:
            return [float(x) for x in output.split(' ') if x]
        return [0, 0]

    def _get_android_version(self):
        """Get the Android Version such as 5.0.1, this method equals method self.get_device_os_version."""
        cmd = ['adb', '-s', self.device, 'shell', 'getprop ro.build.version.release']
        output = self._exec(cmd).strip()
        return output

    def get_app_uid(self, package_name):
        """Get app's uid, if app is not installed, return None."""
        cmd = ['adb', '-s', self.device, 'shell', 'dumpsys package %s | grep userId=' % package_name]
        output = self._exec(cmd)
        candidate = self.re_uid.findall(output)
        return candidate[0] if candidate else None

    def get_current_activity(self):
        """Alias of method self.get_focused_app_window_token."""
        return self.get_focused_app_window_token()

    def get_focused_app_window_token(self):
        """Get the focused app package name as well as its activity."""
        cmd = ['adb', '-s', self.device, 'shell', 'dumpsys window windows | grep -E "mCurrentFocus|mFocusedApp"']
        output = self._exec(cmd)
        token = self.re_focused_app_window_token.findall(output)
        return token[0] if token else None

    def get_pid(self, package_name):
        """Get app's pid."""
        pid = self._ps(package_name).get('pid', None)
        return int(pid) if pid else pid

    # ------------------------------ Get Device Info ------------------------------

    def _get_device_prop(self, prop):
        """Don't call this method directly, using other proper methods builtin instead."""
        cmd = ['adb', '-s', self.device, 'shell', 'getprop %s' % prop]
        return self._exec(cmd).strip()

    def find_device_property_like(self, regexp):
        """Find device properties via regexp."""
        properties = self.get_device_all_properties().items()
        pattern = re.compile(regexp)
        result = {}
        for item in properties:
            for i in item:
                if pattern.findall(i):
                    result.update((item,))
                    break
        return result

    @staticmethod
    def list_devices():
        """List all devices attached."""
        cmd = ['adb', 'devices']
        output = ADB._exec(cmd).strip()
        return [x.split("\t")[0] for x in output.splitlines()[1:]]

    def get_device_all_properties(self):
        """Get info of device."""
        cmd = ['adb', '-s', self.device, 'shell', 'getprop']
        output = self._exec(cmd)
        properties = {}
        if output is not None:
            lines = output.splitlines()
            for line in lines:
                results = self.re_device_properties.findall(line.strip())
                if results:
                    properties.update(dict([results[0]]))
        return properties

    def get_device_baseband(self):
        """Get device baseband, e.g.:  M9615A-CEFWMAZM-2.0.1701.04"""
        return self._get_device_prop("gsm.version.baseband")

    def get_device_build_description(self):
        """Get device build description, e.g.: occam-user 5.0 LRX21T 1576899 release-keys"""
        return self._get_device_prop("ro.build.description")

    def get_device_build_id(self):
        """Return device id such as HuaweiP6-C00."""
        return self._get_device_prop("ro.build.id")

    def get_device_display_id(self):
        """This is similar to method self.get_device_build_id."""
        return self._get_device_prop("ro.build.display.id")

    def get_device_name(self):
        """Return product name such as P6-C00."""
        return self._get_device_prop("ro.product.name")

    def get_device_os_sdk(self):
        """Return Android API level such as 17 for Android 4.2."""
        return self._get_device_prop("ro.build.version.sdk")

    def get_device_os_version(self):
        """Return Android OS Version such as 4.4."""
        return self._get_device_prop("ro.build.version.release")

    def get_device_product_model(self):
        """Get the device model, e.g.: Nexus 4"""
        return self._get_device_prop("ro.product.model")

    def get_device_serial_number(self):
        """This is what the command 'adb devices' returns."""
        return self._get_device_prop("ro.serialno")

    def get_device_wlan_ip_address(self):
        """Get device IP address in a WIFI network."""
        return self._get_device_prop("dhcp.wlan0.ipaddress")

    def get_imei(self):
        """Get phone imei."""
        output = self._adb_shell('dumpsys', 'iphonesubinfo')
        m = re.search(r'\d{15}', output)
        if m is not None:
            return m.group(0)

    # ------------------------------ Get APK Info ------------------------------
    @staticmethod
    def _dump_badging_apk(apk_path):
        """This method is used to get info about APK."""
        cmd = ['aapt', 'dump', 'badging', apk_path]
        return ADB._exec(cmd)

    @classmethod
    def _get_apk_launchable_component(cls, apk_path):
        return "%s/%s" % (cls.get_apk_launchable_activity(apk_path), cls.get_apk_launchable_activity(apk_path))

    @classmethod
    def get_apk_label(cls, apk_path):
        """Get the APK name displayed on screen."""
        result = cls.re_apk_apk_label.findall(cls._dump_badging_apk(apk_path))
        return result[0] if result else None

    @classmethod
    def get_apk_launchable_activity(cls, apk_path):
        """Get the main activity."""
        result = cls.re_apk_launchable_activity.findall(cls._dump_badging_apk(apk_path))
        return result[0] if result else None

    @classmethod
    def get_apk_package_name(cls, apk_path):
        """Get the APK package name."""
        print cls._dump_badging_apk(apk_path)
        result = cls.re_apk_package_name.findall(cls._dump_badging_apk(apk_path))
        return result[0] if result else None

    @classmethod
    def get_apk_sdk_version(cls, apk_path):
        """Get the APK SDK version."""
        result = cls.re_apk_sdk_version.findall(cls._dump_badging_apk(apk_path))
        return result[0] if result else None

    @classmethod
    def get_apk_version_code(cls, apk_path):
        """Get the APK version code such 1."""
        result = cls.re_apk_version_code.findall(cls._dump_badging_apk(apk_path))
        return result[0] if result else None

    @classmethod
    def get_apk_version_name(cls, apk_path):
        """Get the APK version name such as 8.0.1."""
        result = cls.re_apk_version_name.findall(cls._dump_badging_apk(apk_path))
        return result[0] if result else None

    # ------------------------------ Package Management ------------------------------

    def clear_user_data(self, package_name):
        """Clear application's user data."""
        return self._adb_shell("pm", "clear", package_name)

    def install_apk(self, apk_path):
        """Install app using apk specified with apk_path at development machine."""
        cmd = ['adb', '-s', self.device, 'install', apk_path]
        return self._exec(cmd)

    def is_installed(self, package_name):
        """Check whether or not the app has been installed at device."""
        return package_name in self.list_packages()

    def launch_app(self, package_name, activity_name):
        """Launch app."""
        self._adb_shell("am", "start", "%s/%s" % (package_name, activity_name))
        
    def launch_special_activity(self, package_name, activity_name, page_name):
        """Launch specail activity."""
        self._adb_shell("am", "start", "-n","%s/%s" % (package_name, activity_name),"-e open", page_name)

    def list_packages(self):
        """List all apps installed at device."""
        cmd = ['adb', '-s', self.device, 'shell', 'pm list packages']
        output = self._exec(cmd)
        lines = output.strip().split('\n')
        return [p.split(':')[1].strip() for p in lines]

    def get_screenshot(self, directory=None, filename=None):
        """Get screenshot."""
        if directory is None:
            directory = os.getcwd()
        else:
            directory = os.path.join(os.getcwd(), directory)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        if filename is None:
            filename = "%s%02d" % (time.strftime('%y%m%d_%H%M%S'), random.randint(0, 100))
        if not filename.upper().endswith(".PNG"):
            filename += ".png"

        cmd = ['screencap', '-p', '/sdcard/screenshot.png']
        try:
            self._adb_shell(*cmd)            
            self._exec(['adb', 'pull', '/sdcard/screenshot.png', os.path.join(directory, filename)])
            print os.path.join(directory, filename)
            self._adb_shell(['rm', '/sdcard/screenshot.png'])
            return os.path.join(directory, filename)
        except Exception, e:
            return str(e)

    def remove_folder(self, folder):
        """Remove folder at device.

        Note: you should uninstall the app before you remove folder.
        """
        cmd = ['adb', '-s', self.device, 'shell', 'rm -r %s' % folder]
        return self._exec(cmd)

    def uninstall_apk(self, package_name):
        """Uninstall app from device."""
        cmd = ['adb', '-s', self.device, 'shell', 'pm uninstall %s' % package_name]
        return self._exec(cmd)

    # ------------------------------ User Action ------------------------------

    def press_back(self):
        self.key_back()

    def press_home(self):
        self.key_home()

    def drag(self, start, end, duration, **kwargs):
        args = start + end + (duration * 1000,)
        args = [str(x) for x in args]
        return self._adb_shell("input", "swipe", *args)

    def long_press(self, dx, dy):
        return self.drag((dx, dy), (dx, dy), 5)

    @staticmethod
    def sleep(seconds=0):
        time.sleep(seconds)

    def touch(self, x, y, **kwargs):
        return self._adb_shell("input", "tap", str(x), str(y))

    def type(self, message):
        """Send text to device."""
        return self._adb_shell("input", "text", message.replace(" ", "%s"))

    def wait(self, seconds=0):
        self.sleep(seconds)

    def powerstayon(self, stayon=True):
        if stayon == True:
            self._adb_shell("svc","power","stayon", "true")
        else:
            self._adb_shell("svc","power","stayon", "false")
     
    # need root       
    def wifienableordis(self, enable = True):
        if enable == True:
            self._adb_shell("svc","wifi","enable")
        else:
            self._adb_shell("svc","wifi","disable")
    # ----------------------------- Key Event -----------------------------

    def _keyevent(self, keycode):
        self._adb_shell("input", "keyevent", str(keycode))

    def key_menu(self):
        self._keyevent(82)

    def key_soft_right(self):
        self._keyevent(2)

    def key_home(self):
        self._keyevent(3)

    def key_back(self):
        self._keyevent(4)

    def key_call(self):
        self._keyevent(5)

    def key_end_call(self):
        self._keyevent(6)

    def key_0(self):
        self._keyevent(7)

    def key_1(self):
        self._keyevent(8)

    def key_2(self):
        self._keyevent(9)

    def key_3(self):
        self._keyevent(10)

    def key_4(self):
        self._keyevent(11)

    def key_5(self):
        self._keyevent(12)

    def key_6(self):
        self._keyevent(13)

    def key_7(self):
        self._keyevent(14)

    def key_8(self):
        self._keyevent(15)

    def key_9(self):
        self._keyevent(16)

    def key_star(self):
        """char *"""
        self._keyevent(17)

    def key_pound(self):
        """char #"""
        self._keyevent(18)

    def key_d_pad_up(self):
        """Directional Pad Up key."""
        self._keyevent(19)

    def key_d_pad_down(self):
        """Directional Pad Down key."""
        self._keyevent(20)

    def key_d_pad_left(self):
        """Directional Pad Left key."""
        self._keyevent(21)

    def key_d_pad_right(self):
        """Directional Pad Right key."""
        self._keyevent(22)

    def key_d_pad_center(self):
        """Directional Pad Center key."""
        self._keyevent(23)

    def key_volume_up(self):
        self._keyevent(24)

    def key_volume_down(self):
        self._keyevent(25)

    def key_volume_power(self):
        self._keyevent(26)

    def key_camera(self):
        self._keyevent(27)

    def key_clear(self):
        self._keyevent(28)

    def key_a(self):
        self._keyevent(29)

    def key_b(self):
        self._keyevent(30)

    def key_c(self):
        self._keyevent(31)

    def key_d(self):
        self._keyevent(32)

    def key_e(self):
        self._keyevent(33)

    def key_f(self):
        self._keyevent(34)

    def key_g(self):
        self._keyevent(35)

    def key_h(self):
        self._keyevent(36)

    def key_i(self):
        self._keyevent(37)

    def key_j(self):
        self._keyevent(38)

    def key_k(self):
        self._keyevent(39)

    def key_l(self):
        self._keyevent(40)

    def key_m(self):
        self._keyevent(41)

    def key_n(self):
        self._keyevent(42)

    def key_o(self):
        self._keyevent(43)

    def key_p(self):
        self._keyevent(44)

    def key_q(self):
        self._keyevent(45)

    def key_r(self):
        self._keyevent(46)

    def key_s(self):
        self._keyevent(47)

    def key_t(self):
        self._keyevent(48)

    def key_u(self):
        self._keyevent(49)

    def key_v(self):
        self._keyevent(50)

    def key_w(self):
        self._keyevent(51)

    def key_x(self):
        self._keyevent(52)

    def key_y(self):
        self._keyevent(53)

    def key_z(self):
        self._keyevent(54)

    def key_comma(self):
        self._keyevent(55)

    def key_period(self):
        self._keyevent(56)

    def key_alt_left(self):
        self._keyevent(57)

    def key_alt_right(self):
        self._keyevent(58)

    def key_shift_left(self):
        self._keyevent(59)

    def key_shift_right(self):
        self._keyevent(60)

    def key_tab(self):
        self._keyevent(61)

    def key_space(self):
        self._keyevent(62)

    def key_sym(self):
        self._keyevent(63)

    def key_explorer(self):
        self._keyevent(64)

    def key_enter(self):
        self._keyevent(66)
        
    def key_equals(self):
        """ '=' key."""
        self._keyevent(70)

    def key_mute(self):
        self._keyevent(91)

    def key_escape(self):
        self._keyevent(111)

    def key_f1(self):
        self._keyevent(131)

    def key_f2(self):
        self._keyevent(132)

    def key_f3(self):
        self._keyevent(133)

    def key_f4(self):
        self._keyevent(134)

    def key_f5(self):
        self._keyevent(135)

    def key_f6(self):
        self._keyevent(136)

    def key_f7(self):
        self._keyevent(137)

    def key_f8(self):
        self._keyevent(138)

    def key_f9(self):
        self._keyevent(139)

    def key_f10(self):
        self._keyevent(140)

    def key_f11(self):
        self._keyevent(141)

    def key_f12(self):
        self._keyevent(142)   
    
    def get_cpu_usage(self,package_name):
        '''Get the cpu usage of package name'''
        cmd = ['adb', '-s', self.device, 'shell', ' dumpsys cpuinfo | grep %s'%package_name]
        output = self._exec(cmd).strip()
        cmd = ['adb', '-s', self.device, 'shell', ' dumpsys cpuinfo | grep TOTAL']
        mobile_total = self._exec(cmd).strip()
        mobile_total = float(mobile_total.split('%')[0])

        if output=='':
            return (mobile_total,0,0,0)
        print 'output....',output
        tmp = output.split('%')
        print 'tmp....',tmp
        total = float(tmp[0])
        if total == 0:
            return (mobile_total,0,0,0)
        else:
            user=float(tmp[1][tmp[1].rindex(':')+1:len(tmp[1])].strip())
            kernel=float(tmp[2][tmp[2].rindex('+')+1:len(tmp[2])].strip())
            return (mobile_total,total,user,kernel)

    def start_activity(self,activity):
        cmd = 'am start -n {activity}'.format(activity = activity)
        self._adb_shell(cmd)
        
    '''input  string'''
    def input_text(self,text):
        for i in text:
            if i==" ":
                adb_com="key_"+"space"
                key_event = getattr(adb, adb_com)
                key_event()
            else:
                adb_com="key_"+i
                key_event = getattr(adb, adb_com)
                key_event()
        adb.key_enter()
        time.sleep(3)

    def runwatch(self,d,data):
        times = 50
        print "...................................监控系统弹窗中..................................."
        while True:
            if data == 1:                
                return True
            # d.watchers.reset()
            d.watchers.run()        
            times -= 1
            print times
            if times == 0:
                break
            else:
                time.sleep(0.5)
                
    def install_watch(self,d,pkg_path):
        self.uninstall_apk("com.UCMobile")
        try:
            d.watcher('allowroot').when(text=u'允许').click(text=u'允许')
            d.watcher('allowro').when(text=u'删除').click(text=u'删除')
            d.watcher('allow').when(text=u'同意').click(text=u'同意')
            d.watcher('start_flag').when(text=u'跳过').click(text=u'跳过',className='android.widget.TextView')
            t=threading.Thread(target=self.runwatch,args=(d,0))
            t.setDaemon(True)
            t.start()
            self.install_apk(pkg_path)
            self.launch_app('com.UCMobile','com.uc.browser.InnerUCMobile')
            time.sleep(10)
            #print "start UCMobile time",device.start_app('com.UCMobile','com.uc.browser.InnerUCMobile')
        except Exception,e:
            traceback.print_exc()
            print Exception,":",e
        if d(text=u"跳过"):
            d(text=u"跳过").click(text=u'跳过',className='android.widget.TextView')
        print "install success"
        
        
    def uc_openwindow(self,window):
        '''
        ex:account,appmgmt,bmk,bmkmgmt,clip,file,search具体参照ucinitent调用说明
        '''
        cmd=" am start -n com.UCMobile/.main.UCMobile -e open "+window
        self._adb_shell(cmd)
        
        
    def uc_clickfunc(self,func):
        '''
        ex:点击home等操作，具体可用点击参照ucintent说明
        '''
        cmd=" am start -n com.UCMobile/.main.UCMobile -e click "+func
        self._adb_shell(cmd)

class ADBException(Exception):
    pass

class ADBNoDeviceFoundException(ADBException):
    pass

if __name__ == '__main__':
    adb = ADB()
    adb.wifienableordis(False)
