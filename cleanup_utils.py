import os
import shutil


def main() -> None:
    """Utility script to reorganize helper modules and clean caches."""
    project_root = os.path.dirname(__file__)
    print(f"[ROOT] Project root detected: {project_root}")

    utils_path = os.path.join(project_root, "utils")
    widgets_path = os.path.join(project_root, "widgets")
    config_path = os.path.join(project_root, "config")

    # 1. Move GUI-related utility files
    print("\n[STEP] Moving GUI-related utility files...")
    relocations = {
        "ui_helpers.py": widgets_path,
        "theme_helpers.py": config_path,
    }

    os.makedirs(widgets_path, exist_ok=True)
    os.makedirs(config_path, exist_ok=True)

    for filename, target_dir in relocations.items():
        src = os.path.join(utils_path, filename)
        dst = os.path.join(target_dir, filename)
        if os.path.exists(src):
            shutil.move(src, dst)
            print(f"[OK] Moved {filename} -> {target_dir}")
        else:
            print(f"[WARN] {filename} not found in utils/. Nothing moved.")

    # 2. Merge time_utils.py into time_helpers.py (if both exist)
    print("\n[STEP] Checking for time_helpers.py and time_utils.py...")
    time_helpers = os.path.join(utils_path, "time_helpers.py")
    time_utils = os.path.join(utils_path, "time_utils.py")

    if os.path.exists(time_helpers) and os.path.exists(time_utils):
        with open(time_helpers, "a", encoding="utf-8") as helpers_file, open(
            time_utils, encoding="utf-8"
        ) as utils_file:
            helpers_file.write("\n\n# --- Merged from time_utils.py ---\n")
            helpers_file.write(utils_file.read())
        os.remove(time_utils)
        print(
            "[OK] Merged time_utils.py into time_helpers.py and "
            "deleted the original."
        )
    elif not os.path.exists(time_helpers):
        print("[WARN] time_helpers.py not found.")
    elif not os.path.exists(time_utils):
        print("[WARN] time_utils.py not found.")

    # 3. Delete __pycache__ directory
    print("\n[STEP] Cleaning up __pycache__/ from utils/...")
    pycache_path = os.path.join(utils_path, "__pycache__")
    if os.path.exists(pycache_path):
        shutil.rmtree(pycache_path)
        print("[OK] Deleted __pycache__/")
    else:
        print("[INFO] No __pycache__/ directory found.")

    # 4. Final report
    print("\n[INFO] Remaining files in utils/:")
    if os.path.exists(utils_path):
        for item in os.listdir(utils_path):
            print("-", item)
    else:
        print("[WARN] utils/ folder not found.")

    print("\n[OK] Cleanup complete.")


if __name__ == "__main__":
    main()
