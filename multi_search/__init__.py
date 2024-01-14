from multi_search.multi_search import MultiSearch


__main = MultiSearch()


def on_load(*args, **kwargs):
    __main.on_load()
