
import importlib.util

def check_module(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        print(f"{module_name} is not installed.")
    else:
        print(f"{module_name} is installed.")

if __name__ == "__main__":
    check_module("exiftool")