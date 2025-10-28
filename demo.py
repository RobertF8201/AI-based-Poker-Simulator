def mystry(n):
    if n == 0:
        return 0
    return n + mystry(n-1)

print(mystry(5))