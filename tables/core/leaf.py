import sys
import numpy as np
from .node import Node
from tables.utils import byteorders
from ..exceptions import ClosedNodeError


class Leaf(Node):
    @property
    def byteorder(self):
        return byteorders[self.dtype.byteorder]

    @property
    def chunkshape(self):
        return self.backend.chunks

    @property
    def dtype(self):
        return self.backend.dtype

    @property
    def flavor(self):
        return self._flavor

    @flavor.setter
    def flavor(self, value):
        self._flavor = self.attrs['FLAVOR'] = value

    @property
    def shape(self):
        return self.backend.shape

    @property
    def size_on_disk(self):
        return self.backend.size_on_disk

    def __len__(self):
        return len(self.backend)

    @property
    def maindim(self):
        """The dimension along which iterators work.

        Its value is 0 (i.e. the first dimension) when the dataset is not
        extendable, and self.extdim (where available) for extendable ones.
        """

        if self.extdim < 0:
            return 0  # choose the first dimension
        return self.extdim

    @property
    def ndim(self):
        return len(self.shape)

    @property
    def nrows(self):
        if len(self.shape) > 0:
            return int(self.shape[self.maindim])
        # Scalar dataset
        else:
            return 1 if self.shape == () else len(self)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._flavor = None

    def __getitem__(self, item):
        if not self._v_file._isopen:
            raise ClosedNodeError
        try:
            arr = self.backend.__getitem__(item)
        except ValueError:  # invalid selection
            arr = self.backend.__getitem__(slice(0, 0, 1))
        if isinstance(arr, np.ndarray) and byteorders[arr.dtype.byteorder] != sys.byteorder:
            arr = arr.byteswap(True)
            arr.dtype = arr.dtype.newbyteorder('=')
        return arr


    def __setitem__(self, item, value):
        if not self._v_file._isopen:
            raise ClosedNodeError
        try:
            return self.backend.__setitem__(item, value)
        except TypeError:
            if not hasattr(value, 'astype'):
                value = np.asarray(value)
            return self.backend.__setitem__(item, value.astype(self.dtype))

    def get_attr(self, attr):
        return self.attrs[attr]

    def _process_range(self, start, stop, step, dim=None, warn_negstep=True):
        # This method is appropriate for calls to __getitem__ methods
        if dim is None:
            nrows = self.nrows
        else:
            nrows = self.shape[dim]
        if warn_negstep and step and step < 0:
            raise ValueError("slice step cannot be negative")
        return slice(start, stop, step).indices(nrows)

    def _process_range_read(self, start, stop, step, warn_negstep=True):
        # This method is appropriate for calls to read() methods
        nrows = self.nrows
        if start is not None and stop is None and step is None:
            # Protection against start greater than available records
            # nrows == 0 is a special case for empty objects
            if nrows > 0 and start >= nrows:
                raise IndexError("start of range (%s) is greater than "
                                 "number of rows (%s)" % (start, nrows))
            step = 1
            if start == -1:  # corner case
                stop = nrows
            else:
                stop = start + 1
        # Finally, get the correct values (over the main dimension)
        start, stop, step = self._process_range(start, stop, step,
                                                warn_negstep=warn_negstep)
        return (start, stop, step)

    def flush(self):
        pass

    def __str__(self):
        """The string representation for this object is its pathname in the
        HDF5 object tree plus some additional metainfo."""

        # Get this class name
        classname = self.__class__.__name__
        # The title
        title = self.title
        # The filters
        filters = ""
        if self.filters.fletcher32:
            filters += ", fletcher32"
        if self.filters.complevel:
            if self.filters.shuffle:
                filters += ", shuffle"
            if self.filters.bitshuffle:
                filters += ", bitshuffle"
            filters += ", %s(%s)" % (self.filters.complib,
                                     self.filters.complevel)
        return "%s (%s%s%s) %r" % \
               (self._v_pathname, classname, self.shape, filters, title)
