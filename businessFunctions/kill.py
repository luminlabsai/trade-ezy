import subprocess
import re

def kill_ports_on_7071():
    try:
        # Run the lsof command to list processes using port 7071
        result = subprocess.run(["lsof", "-i", ":7071"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check if the command failed
        if result.returncode != 0:
            print(f"Error running lsof: {result.stderr}")
            return
        
        # Parse the output to extract process IDs
        pids = set()  # Use a set to avoid duplicate PIDs
        for line in result.stdout.splitlines()[1:]:  # Skip the header line
            parts = line.split()
            if len(parts) >= 2:
                pid = parts[1]
                if pid.isdigit():
                    pids.add(pid)
        
        if not pids:
            print("No processes found using port 7071.")
            return
        
        # Kill each PID
        for pid in pids:
            try:
                subprocess.run(["kill", "-9", pid], check=True)
                print(f"Successfully killed process with PID: {pid}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to kill process with PID: {pid}. Error: {e}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    kill_ports_on_7071()
