from interpreterv3 import Interpreter

def main():
    f = open("test.txt")
    program = f.readlines()
    i = Interpreter()
    i.run(program)

if __name__ == "__main__":
    main()