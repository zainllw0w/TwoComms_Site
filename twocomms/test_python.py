#!/usr/bin/env python3
print("Content-Type: text/html\n")
print("<h1>Python работает!</h1>")
print("<p>Время:", __import__('datetime').datetime.now(), "</p>")
print("<p>Версия Python:", __import__('sys').version, "</p>")
