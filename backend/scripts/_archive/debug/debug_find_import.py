import os

def find_bad_import(start_dir):
    with open("bad_imports_v2.log", "w", encoding="utf-8") as log:
        print(f"Scanning {start_dir}...")
        for root, dirs, files in os.walk(start_dir):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Check if file interacts with schemas.broker AND mentions BrokerAccount
                            if "app.schemas.broker" in content and "BrokerAccount" in content:
                                log.write(f"POSSIBLE MATCH: {path}\n")
                                # Print context
                                log.write("  Context:\n")
                                lines = content.splitlines()
                                for i, line in enumerate(lines):
                                    if "app.schemas.broker" in line or "BrokerAccount" in line:
                                        log.write(f"    {i+1}: {line.strip()}\n")
                                log.write("-" * 40 + "\n")
                    except Exception as e:
                        print(f"Could not read {path}: {e}")

if __name__ == "__main__":
    find_bad_import(".")
