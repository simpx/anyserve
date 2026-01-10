import pickle
from typing import Generic, TypeVar, Optional, Any as PyAny
from anyserve.core import get_core

T = TypeVar("T")

class Any(Generic[T]):
    """
    A reference to a distributed object.
    It holds the object's UUID and the ID of the instance that owns it.
    """
    def __init__(self, obj: Optional[T] = None, _uuid: str = None, _owner: str = None):
        """
        Create an Any reference.
        
        Args:
            obj: The object to store. If provided, it will be serialized and stored immediately.
            _uuid: Internal use. The UUID of the existing object.
            _owner: Internal use. The instance ID where the object is stored.
        """
        if obj is not None:
            # Create new object
            data = pickle.dumps(obj)
            core = get_core()
            self.uuid = core.put_object(data)
            self.owner = core.get_instance_id()
        else:
            # Reference to existing object
            if _uuid is None or _owner is None:
                raise ValueError("Must provide either obj or (_uuid and _owner)")
            self.uuid = _uuid
            self.owner = _owner

    def get(self) -> T:
        """
        Fetch the object from the owner instance and deserialize it.
        This is where the network/disk IO happens.
        """
        core = get_core()
        # In a real system, this might fetch from remote if owner != self
        data = core.get_object(self.uuid, self.owner)
        return pickle.loads(bytes(data))

    def __repr__(self):
        return f"<Any uuid={self.uuid} owner={self.owner}>"

    # Make Any itself picklable so it can be passed as an argument
    def __getstate__(self):
        return {"uuid": self.uuid, "owner": self.owner}

    def __setstate__(self, state):
        self.uuid = state["uuid"]
        self.owner = state["owner"]
