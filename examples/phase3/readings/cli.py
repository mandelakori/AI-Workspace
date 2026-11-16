import json
import sys

from summary import summarize


def main():
    print(summarize(json.load(sys.stdin)))


if __name__ == "__main__":
    main()
