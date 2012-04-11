"""
This module aims to contain the method specific to the REST interface.
These are extensions which are not directly contained in WMCore.REST module.
Collecting all here since aren't supposed to be many.
"""
# WMCore dependecies here
from WMCore.REST.Validation import _validate_one
from WMCore.REST.Error import RESTError, InvalidParameter

# external dependecies here
import tarfile
import hashlib
import cStringIO
import cherrypy
from os import fstat

# 100MB is the maximum allowed size of a single file
FILE_SIZE_LIMIT = 104857600
# 0.5MB is the maximum limit for file completely loaded into memory
FILE_MEMORY_LIMIT = 512*1024

###### authz_login_valid is currently duplicatint CRABInterface.RESTExtension . A better solution
###### should be found for authz_*
def authz_login_valid():
    if not cherrypy.request.user['login']:
        raise cherrypy.HTTPError(403, "You are not allowed to access this resource.")


def _check_file(argname, val, hashkey):
    """Check that `argname` `val` is a tar file and that provided 'hashkey`
       matches with the hashkey calculated on the `val`.

       :arg str argname: name of the argument
       :arg file val: the file object
       :arg str hashkey: the sha256 hexdigest of the file, calculated over the tuple
                         (name, size, mtime, uname) of all the tarball members
       :return: the val if the validation passes."""
    # checking that is a valid file or an input string
    # note: the input string is generated on client side just when the input file is empty
    if not hasattr(val, 'file') or not (isinstance(val.file, file) or isinstance(val.file, cStringIO.StringIO)):
        raise InvalidParameter("Incorrect inputfile parameter")
    elif isinstance(val.file, file):
        if fstat(val.file.fileno()).st_size > FILE_SIZE_LIMIT:
            raise InvalidParameter('File is bigger then allowed limit of %d' % FILE_SIZE_LIMIT)
    elif isinstance(val.file, cStringIO.StringIO):
        # in this case file content is in memory instead of a file object handle
        val.file.seek(0,2)
        insize = val.file.tell()
        val.file.seek(0)
        if insize > FILE_MEMORY_LIMIT:
            raise InvalidParameter('File too large to be completely loaded into memory.')

    digest = None
    try:
        tar = tarfile.open(fileobj=val.file, mode='r')
        lsl = [(x.name, int(x.size), int(x.mtime), x.uname) for x in tar.getmembers()]
        hasher = hashlib.sha256(str(lsl))
        digest = hasher.hexdigest()
    except tarfile.ReadError:
        raise InvalidParameter('File is not a .tgz file.')
    if not digest or hashkey != digest:
        raise ChecksumFailed("Checksums do not match")
    return val

class ChecksumFailed(RESTError):
    "Checksum calculation failed, file transfer problem."
    http_code = 400
    app_code = 302
    message = "Input file hashkey mismatch"

def validate_file(argname, param, safe, hashkey, optional=False):
    """Validates that an argument is a file and matches the hashkey.

    Checks that an argument named `argname` exists in `param.kwargs`
    and it is a tar file which matches the provided hashkey. If
    successful the string is copied into `safe.kwargs` and the value
    is removed from `param.kwargs`.

    If `optional` is True, the argument is not required to exist in
    `param.kwargs`; None is then inserted into `safe.kwargs`. Otherwise
    a missing value raises an exception."""
    _validate_one(argname, param, safe, _check_file, optional, safe.kwargs[hashkey])