def import_by_string(name):
    # https://stackoverflow.com/a/547867
    components = name.split(".")
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod
