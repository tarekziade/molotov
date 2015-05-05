from ailoads.fmwk import runner


def main():
    from ailoads import example
    res = runner(10, 60)
    tok, tfailed = 0, 0

    for ok, failed in res:
        tok += ok
        tfailed += failed

    print('')
    print('%d OK, %d Failed' % (tok, tfailed))


if __name__ == '__main__':
    main()
