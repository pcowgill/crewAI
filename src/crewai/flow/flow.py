from typing import Any, Callable, Dict, Generic, List, Type, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T", bound=Union[BaseModel, Dict[str, Any]])


class FlowMeta(type):
    def __new__(mcs, name, bases, dct):
        cls = super().__new__(mcs, name, bases, dct)

        start_methods = []
        listeners = {}

        for attr_name, attr_value in dct.items():
            if hasattr(attr_value, "__is_start_method__"):
                start_methods.append(attr_name)
            if hasattr(attr_value, "__trigger_methods__"):
                for trigger in attr_value.__trigger_methods__:
                    trigger_name = trigger.__name__ if callable(trigger) else trigger
                    if trigger_name not in listeners:
                        listeners[trigger_name] = []
                    listeners[trigger_name].append(attr_name)

        setattr(cls, "_start_methods", start_methods)
        setattr(cls, "_listeners", listeners)

        # Inject the state type hint
        if "initial_state" in dct:
            initial_state = dct["initial_state"]
            if isinstance(initial_state, type) and issubclass(initial_state, BaseModel):
                cls.__annotations__["state"] = initial_state
            elif isinstance(initial_state, dict):
                cls.__annotations__["state"] = Dict[str, Any]

        return cls


class Flow(Generic[T], metaclass=FlowMeta):
    _start_methods: List[str] = []
    _listeners: Dict[str, List[str]] = {}
    initial_state: Union[Type[T], T, None] = None

    def __init__(self):
        self._methods: Dict[str, Callable] = {}
        self._state = self._create_initial_state()

        for method_name in dir(self):
            if callable(getattr(self, method_name)) and not method_name.startswith(
                "__"
            ):
                self._methods[method_name] = getattr(self, method_name)

    def _create_initial_state(self) -> T:
        if self.initial_state is None:
            return {}  # type: ignore
        elif isinstance(self.initial_state, type):
            return self.initial_state()
        else:
            return self.initial_state

    @property
    def state(self) -> T:
        return self._state

    def run(self):
        if not self._start_methods:
            raise ValueError("No start method defined")

        for start_method in self._start_methods:
            result = self._methods[start_method]()
            self._execute_listeners(start_method, result)

    def _execute_listeners(self, trigger_method: str, result: Any):
        if trigger_method in self._listeners:
            for listener in self._listeners[trigger_method]:
                try:
                    listener_result = self._methods[listener](result)
                    self._execute_listeners(listener, listener_result)
                except Exception as e:
                    print(f"Error in method {listener}: {str(e)}")
                    return


def start():
    def decorator(func):
        func.__is_start_method__ = True
        return func

    return decorator


def listen(*trigger_methods):
    def decorator(func):
        func.__trigger_methods__ = trigger_methods
        return func

    return decorator