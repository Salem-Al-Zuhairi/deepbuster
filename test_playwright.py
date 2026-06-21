import os

print("Checking /usr/share/nodejs/playwright:")
try:
    print(os.listdir("/usr/share/nodejs/playwright"))
except Exception as e:
    print("Error:", e)
