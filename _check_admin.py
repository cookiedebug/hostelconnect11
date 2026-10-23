import urllib.request
import urllib.error
import http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
req = urllib.request.Request(
    "http://127.0.0.1:5000/login",
    data=b"email=admin%40hostelconnect.local&password=admin123",
    method="POST",
)
req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    opener.open(req)
except urllib.error.HTTPError:
    pass
html = opener.open("http://127.0.0.1:5000/admin").read().decode("utf-8", "replace")
checks = [
    "My pictures",
    "Hostel pictures",
    "Upload hostel pictures",
    "Drop your pictures",
    "+ Add Accommodation",
]
for item in checks:
    print(item, "OK" if item in html else "MISSING")
form = opener.open("http://127.0.0.1:5000/manager/hostel/new").read().decode("utf-8", "replace")
print("ADMIN_FORM", "ADMINISTRATOR" in form and "multipart/form-data" in form)
