from interpreterv2 import Interpreter

def main():
    f = open("Project2\/test.txt")
    program = f.readlines()
    i = Interpreter()
    i.run(program)

if __name__ == "__main__":
    main()