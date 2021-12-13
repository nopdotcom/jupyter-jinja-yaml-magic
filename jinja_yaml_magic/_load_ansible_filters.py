# This is probably not the ideal way to gather Ansible filters, but it
# works.
#
# Isolated to a separate file to avoid hitting critical mass of hackery
# in one place.

import ansible.plugins.loader as loader


def _load_ansible_filters(plugin_root_dir="plugins/filter"):
    # TODO: Figure out what that last argument really does
    jl = loader.Jinja2Loader("FilterModule", "ansible.plugins.filter", None, ".")
    jl.add_directory(plugin_root_dir)
    filters = {}
    for mod in jl.all():
        for name, filter in mod.filters().items():
            filters[name] = filter
    return filters
