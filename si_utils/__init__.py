__version__ = '0.1.1'


if __name__ == "__main__":
    import os
    if os.environ.get('PYDEBUG'):
        # we're in a debugger session
        exit()
    try:
        pass  # cli code goes here
    except KeyboardInterrupt:
        print("Aborted!")
        exit()
