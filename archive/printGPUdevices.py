import Metashape
# ... (rest of your script setup, argument parsing etc.) ...

mask = 2 ** len(Metashape.app.enumGPUDevices()) - 1
Metashape.app.gpu_mask = mask

# Add the print statement here:
devices = Metashape.app.enumGPUDevices()
print("Detected GPUs in Metashape:")
for i, device in enumerate(devices):
    print(f"  GPU {i+1}: {device['name']}") # Accessing 'name' as a dictionary key
print("----------------------") # Separator for clarity


# ... (rest of your script) ...