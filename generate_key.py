import secrets
import string
import argparse

def generate_key(length):
    """Generate a random alphanumeric string of a specified length."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

def main():
    parser = argparse.ArgumentParser(description="Generate random API keys or secret strings.")
    parser.add_argument("-l", "--length", type=int, default=32,
                        help="Length of the key(s) to generate (default: 32)")
    parser.add_argument("-c", "--count", type=int, default=1,
                        help="Number of keys to generate (default: 1)")
    
    args = parser.parse_args()

    if args.length <= 0:
        print("Error: Key length must be a positive integer.")
        return
    if args.count <= 0:
        print("Error: Key count must be a positive integer.")
        return

    print(f"Generating {args.count} key(s) of length {args.length}:")
    for i in range(args.count):
        key = generate_key(args.length)
        print(key)

if __name__ == "__main__":
    main()
