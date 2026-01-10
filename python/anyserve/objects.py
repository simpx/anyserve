import pickle
from typing import Generic, TypeVar, Optional, Any as PyAny
from anyserve.core import get_core

T = TypeVar("T")

class Any(Generic[T]):
    """
    A reference to a distributed object.
    It holds the object's UUID and the address of the instance that owns it.
    """
    def __init__(self, obj: Optional[T] = None, _uuid: str = None, _owner_addr: str = None):
        """
        Create an Any reference.
        
        Args:
            obj: The object to store. If provided, it will be serialized and stored immediately.
            _uuid: Internal use. The UUID of the existing object.
            _owner_addr: Internal use. The address (ip:port) of the instance where the object is stored.
        """
        if obj is not None:
            # Create new object
            data = pickle.dumps(obj)
            core = get_core()
            self.uuid = core.put_object(data)
            self.owner_addr = core.get_address()
        else:
            # Reference to existing object
            if _uuid is None or _owner_addr is None:
                raise ValueError("Must provide either obj or (_uuid and _owner_addr)")
            self.uuid = _uuid
            self.owner_addr = _owner_addr

    def get(self) -> T:
        """
        Fetch the object from the owner instance and deserialize it.
        This is where the network/disk IO happens.
        """
        core = get_core()
        # Fetch from remote using network address
        data = core.get_object_network(self.uuid, self.owner_addr)
        return pickle.loads(bytes(data))

    def __repr__(self):
        return f"<Any uuid={self.uuid} owner_addr={self.owner_addr}>"

    # Make Any itself picklable so it can be passed as an argument
    def __getstate__(self):
        return {"uuid": self.uuid, "owner_addr": self.owner_addr}

    def __setstate__(self, state):
        self.uuid = state["uuid"]
        self.owner_addr = state["owner_addr"]
