from dotenv import load_dotenv
import os

load_dotenv()

def main():
    print("Hello from langgraph!")


if __name__ == "__main__":
    main()
print("Environment variables loaded:")
for key, value in os.environ.items():
    print(f"{key}: {value}")