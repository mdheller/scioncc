#!/usr/bin/env python

# Ion utility for generating interfaces from object definitions (and vice versa).

__author__ = 'Adam R. Smith'
__license__ = 'Apache 2.0'

import datetime
import fnmatch
import inspect
import os
import re
import sys

import yaml
import hashlib
import argparse

from pyon.service.service import BaseService
from pyon.util.containers import named_any

# Do not remove any of the imports below this comment!!!!!!
from pyon.core.object import IonYamlLoader, service_name_from_file_name
from pyon.util import yaml_ordered_dict

class IonServiceDefinitionError(Exception):
    pass

templates = {
      'file':
'''#!/usr/bin/env python
#
# File generated on {when_generated}
#

from zope.interface import Interface, implements

from collections import OrderedDict, defaultdict

from pyon.service.service import BaseService

{classes}
'''
    , 'class':
'''class I{name}(Interface):
{classdocstring}
{methods}
'''
'''class Base{name}(BaseService):
    implements(I{name})
{classdocstring}
{servicename}
{dependencies}
{classmethods}
'''
    , 'clssdocstr':
'    """{classdocstr}\n\
    """'
    , 'svcname':
'    name = \'{name}\''
    , 'depends':
'    dependencies = {namelist}'
    , 'method':
'''
    def {name}({args}):
        {methoddocstring}
        # Return Value
        # ------------
        # {outargs}
        pass
'''
    , 'arg': '{name}={val}'
    , 'methdocstr':
'"""{methoddocstr}\n\
        """'
}

def build_args_str(_def, include_self=True):
    # Handle case where method has no parameters
    args = []
    if include_self: args.append('self')
        
    for key,val in (_def or {}).iteritems():
        if isinstance(val, basestring):
            val = "'%s'" % (val)
        elif isinstance(val, datetime.datetime):
            # TODO: generate the datetime code
            val = "'%s'" % (val)
        # For collections, default to an empty collection of the same base type
        elif isinstance(val, list):
            val = []
        elif isinstance(val, dict):
            val = {}
        args.append(templates['arg'].format(name=key, val=val))
        
    args_str = ', '.join(args)
    return args_str

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--force', action='store_true', help='Do not do MD5 comparisons, always generate new files')
    parser.add_argument('-d', '--dryrun', action='store_true', help='Do not generate new files, just print status and exit with 1 if changes need to be made')
    opts = parser.parse_args()

    if os.getcwd().endswith('scripts'):
        sys.exit('This script needs to be run from the pyon root.')

    service_dir, interface_dir = 'obj/services', 'interface'
    if not os.path.exists(interface_dir):
        os.makedirs(interface_dir)

    # Clear old generated files
    files = os.listdir(interface_dir)
    for file in fnmatch.filter(files, '*.pyc'):
    #for file in fnmatch.filter(files, '*.py') + fnmatch.filter(files, '*.pyc'):
        os.unlink(os.path.join(interface_dir, file))

    open(os.path.join(interface_dir, '__init__.py'), 'w').close()

    # Load data yaml files in case services define interfaces
    # in terms of common data objects
    yaml_file_re = re.compile('(obj)/(.*)[.](yml)')
    data_dir = 'obj/data'
    entag = u'!enum'
    yaml.add_constructor(entag, lambda loader, node: {})
    for root, dirs, files in os.walk(data_dir):
        for filename in fnmatch.filter(files, '*.yml'):
            yaml_file = os.path.join(root, filename)
            file_match = yaml_file_re.match(yaml_file)
            if file_match is None: continue

            yaml_text = open(yaml_file, 'r').read()
            defs = yaml.load_all(yaml_text, Loader=IonYamlLoader)
            for def_set in defs:
                for name,_def in def_set.iteritems():
                    tag = u'!%s' % (name)
                    yaml.add_constructor(tag, lambda loader, node: {})
                    xtag = u'!Extends_%s' % (name)
                    yaml.add_constructor(xtag, lambda loader, node: {})

    svc_signatures = {}
    sigfile = os.path.join('interface', '.svc_signatures.yml')
    if os.path.exists(sigfile):
        with open(sigfile, 'r') as f:
            cnts = f.read()
            svc_signatures = yaml.load(cnts)

    count = 0

    currtime = str(datetime.datetime.today())
    # Generate the new definitions, for now giving each
    # yaml file its own python service
    for root, dirs, files in os.walk(service_dir):
        for filename in fnmatch.filter(files, '*.yml'):
            yaml_file = os.path.join(root, filename)
            file_match = yaml_file_re.match(yaml_file)
            if '.svc_signatures' in filename: continue
            if file_match is None: continue

            file_path = file_match.group(2)
            interface_base, interface_name = os.path.dirname(file_path), os.path.basename(file_path)
            interface_file = os.path.join('interface', interface_base, 'i%s.py' % interface_name)

            parent_dir = os.path.dirname(interface_file)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir)
                parent = parent_dir
                while True:
                    # Add __init__.py files to parent dirs as necessary
                    curdir = os.path.split(os.path.abspath(parent))[1]
                    if curdir == 'services':
                        break
                    else:
                        parent = os.path.split(os.path.abspath(parent))[0]

                        pkg_file = os.path.join(parent, '__init__.py')
                        if not os.path.exists(pkg_file):
                            open(pkg_file, 'w').close()

            pkg_file = os.path.join(parent_dir, '__init__.py')
            if not os.path.exists(pkg_file):
                open(pkg_file, 'w').close()

            with open(yaml_file, 'r') as f:
                yaml_text = f.read()
                m = hashlib.md5()
                m.update(yaml_text)
                cur_md5 = m.hexdigest()

                if yaml_file in svc_signatures and not opts.force:
                    if cur_md5 == svc_signatures[yaml_file]:
                        print "Skipping   %40s (md5 signature match)" % interface_name
                        continue

                if opts.dryrun:
                    count += 1
                    print "Changed    %40s (needs update)" % interface_name
                    continue

                # update signature set
                svc_signatures[yaml_file] = cur_md5
                print 'Generating %40s -> %s' % (interface_name, interface_file)

            defs = yaml.load_all(yaml_text)
            for def_set in defs:
                # Handle object definitions first; make dummy constructors so tags will parse
                if 'obj' in def_set:
                    for obj_name in def_set['obj']:
                        tag = u'!%s' % (obj_name)
                        yaml.add_constructor(tag, lambda loader, node: {})
                    continue

                service_name = def_set.get('name', None)
                class_docstring = def_set.get('docstring', "class docstring")
                class_docstring_lines = class_docstring.split('\n')

                # Annoyingly, we have to hand format the doc strings to introduce
                # the correct indentation on multi-line strings           
                first_time = True
                class_docstring_formatted = ""
                for i in range(len(class_docstring_lines)):
                    class_docstring_line = class_docstring_lines[i]
                    # Potentially remove excess blank line
                    if class_docstring_line == "" and i == len(class_docstring_lines) - 1:
                        break
                    if first_time:
                        first_time = False
                    else:
                        class_docstring_formatted += "\n    "
                    class_docstring_formatted += class_docstring_line

                dependencies = def_set.get('dependencies', None)
                methods, class_methods = [], []

                # It seems that despite the get with default arg, there still can be None resulting (YAML?)
                meth_list = def_set.get('methods', {}) or {}
                for op_name,op_def in meth_list.iteritems():
                    if not op_def: continue
                    def_docstring, def_in, def_out = op_def.get('docstring', "method docstring"), op_def.get('in', None), op_def.get('out', None)
                    docstring_lines = def_docstring.split('\n')

                    # Annoyingly, we have to hand format the doc strings to introduce
                    # the correct indentation on multi-line strings           
                    first_time = True
                    docstring_formatted = ""
                    for i in range(len(docstring_lines)):
                        docstring_line = docstring_lines[i]
                        # Potentially remove excess blank line
                        if docstring_line == "" and i == len(docstring_lines) - 1:
                            break
                        if first_time:
                            first_time = False
                        else:
                            docstring_formatted += "\n        "
                        docstring_formatted += docstring_line

                    args_str, class_args_str = build_args_str(def_in, False), build_args_str(def_in, True)
                    docstring_str = templates['methdocstr'].format(methoddocstr=docstring_formatted)
                    outargs_str = '\n        # '.join(yaml.dump(def_out).split('\n'))

                    methods.append(templates['method'].format(name=op_name, args=args_str, methoddocstring=docstring_str, outargs=outargs_str))
                    class_methods.append(templates['method'].format(name=op_name, args=class_args_str, methoddocstring=docstring_str, outargs=outargs_str))

                if service_name is None:
                    raise IonServiceDefinitionError("Service definition file %s does not define name attribute" % yaml_file)
                service_name_str = templates['svcname'].format(name=service_name)
                class_docstring_str = templates['clssdocstr'].format(classdocstr=class_docstring_formatted)
                dependencies_str = templates['depends'].format(namelist=dependencies)
                methods_str = ''.join(methods) or '    pass\n'
                classmethods_str = ''.join(class_methods)
                class_name = service_name_from_file_name(interface_name)
                _class = templates['class'].format(name=class_name, classdocstring=class_docstring_str, servicename=service_name_str, dependencies=dependencies_str,
                                                       methods=methods_str, classmethods=classmethods_str)

                interface_contents = templates['file'].format(classes=_class, when_generated=currtime)
                open(interface_file, 'w').write(interface_contents)

                count+=1

    # write current svc_signatures
    if count > 0 and not opts.dryrun:
        print "Writing signature file to ", sigfile
        with open(sigfile, 'w') as f:
            f.write(yaml.dump(svc_signatures))

        # Load interface base classes
        load_mods("interface/services", True)
        base_subtypes = find_subtypes(BaseService)
        # Load impl classes
        load_mods("ion", False)

    # Generate validation report
    validation_results = "Report generated on " + currtime + "\n"
    load_mods("interface/services", True)
    base_subtypes = find_subtypes(BaseService)
    load_mods("ion", False)
    load_mods("examples", False)
    for base_subtype in base_subtypes:
        base_subtype_name = base_subtype.__module__ + "." + base_subtype.__name__
        compare_methods = {}
        for method_tuple in inspect.getmembers(base_subtype, inspect.ismethod):
            method_name = method_tuple[0]
            method = method_tuple[1]
            # Ignore private methods
            if method_name.startswith("_"):
                continue
            # Ignore methods not implemented in the class
            if method_name not in base_subtype.__dict__:
                continue
            compare_methods[method_name] = method

        # Find implementing subtypes of each base interface
        impl_subtypes = find_subtypes(base_subtype)
        if len(impl_subtypes) == 0:
            validation_results += "\nBase service: %s \n" % base_subtype_name
            validation_results += "  No impl subtypes found\n"
        for impl_subtype in find_subtypes(base_subtype):
            impl_subtype_name = impl_subtype.__module__ + "." + impl_subtype.__name__

            # Compare parameters
            added_class_names = False
            found_error = False
            for key in compare_methods:
                if key not in impl_subtype.__dict__:
                    if not added_class_names:
                        added_class_names = True
                        validation_results += "\nBase service: %s\n" % base_subtype_name
                        validation_results += "Impl subtype: %s\n" % impl_subtype_name
                    validation_results += "  Method '%s' not implemented" % key
                else:
                    base_params = inspect.getargspec(compare_methods[key])
                    impl_params = inspect.getargspec(impl_subtype.__dict__[key])

                    if base_params != impl_params:
                        if not added_class_names:
                            added_class_names = True
                            validation_results += "\nBase service: %s\n" % base_subtype_name
                            validation_results += "Impl subtype: %s\n" % impl_subtype_name
                        validation_results +=  "  Method '%s' implementation is out of sync\n" % key
                        validation_results +=  "    Base: %s\n" % str(base_params)
                        validation_results +=  "    Impl: %s\n" % str(impl_params)

            if found_error == False:
                validation_results += "\nBase service: %s\n" % base_subtype_name
                validation_results += "Impl subtype: %s\n" % impl_subtype_name
                validation_results += "  OK\n"

    reportfile = os.path.join('interface', 'validation_report.txt')
    try:
        os.unlink(reportfile)
    except:
        pass
    print "Writing validation report to '" + reportfile + "'"
    with open(reportfile, 'w') as f:
        f.write(validation_results)

    exitcode = 0
    if count > 0:
        exitcode = 1

    sys.exit(exitcode)

def load_mods(path, interfaces):
    import pkgutil
    import string
    mod_prefix = string.replace(path, "/", ".")

    for mod_imp, mod_name, is_pkg in pkgutil.iter_modules([path]):
        if is_pkg:
            load_mods(path+"/"+mod_name, interfaces)
        else:
            mod_qual = "%s.%s" % (mod_prefix, mod_name)
            try:
                named_any(mod_qual)
            except Exception, ex:
                print "Import module '%s' failed: %s" % (mod_qual, ex)
                if not interfaces:
                    print "Make sure that you have defined an __init__.py in your directory and that you have imported the correct base type"

def find_subtypes(clz):
    res = []
    for cls in clz.__subclasses__():
        assert hasattr(cls,'name'), 'Service class must define name value. Service class in error: %s' % cls
        res.append(cls)
    return res

if __name__ == '__main__':
    main()
