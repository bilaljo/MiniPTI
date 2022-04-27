from Decimation import Decimation


def main():
    decimation = Decimation(file_name="data.bin")
    decimation.read_data()
    for i in range(100):
        print(decimation.ref[i])
        if decimation.ref[i] < 1:
            print(i)
            break
    decimation.read_data()
    for i in range(100):
        print(decimation.ref[i])
        if decimation.ref[i] < 1:
            print(i)
            break


if __name__ == "__main__":
    main()
