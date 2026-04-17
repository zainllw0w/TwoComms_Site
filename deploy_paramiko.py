import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("195.191.24.169", username="qlknpodo", password="trs5m4t1")

commands = [
    "cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull origin main",
    "source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py collectstatic --noinput && python manage.py compress --force",
    "touch /home/qlknpodo/TWC/TwoComms_Site/twocomms/twocomms/wsgi.py"
]

for cmd in commands:
    print(f"Running: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # Wait for the command to finish
    exit_status = stdout.channel.recv_exit_status()
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))

ssh.close()
print("Success")
