from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SpeechRecognitionEvent(_message.Message):
    __slots__ = ("status", "result", "endpoint")
    class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_SUCCESS: _ClassVar[SpeechRecognitionEvent.StatusCode]
        STATUS_NO_SPEECH: _ClassVar[SpeechRecognitionEvent.StatusCode]
        STATUS_ABORTED: _ClassVar[SpeechRecognitionEvent.StatusCode]
        STATUS_AUDIO_CAPTURE: _ClassVar[SpeechRecognitionEvent.StatusCode]
        STATUS_NETWORK: _ClassVar[SpeechRecognitionEvent.StatusCode]
        STATUS_NOT_ALLOWED: _ClassVar[SpeechRecognitionEvent.StatusCode]
        STATUS_SERVICE_NOT_ALLOWED: _ClassVar[SpeechRecognitionEvent.StatusCode]
        STATUS_BAD_GRAMMAR: _ClassVar[SpeechRecognitionEvent.StatusCode]
        STATUS_LANGUAGE_NOT_SUPPORTED: _ClassVar[SpeechRecognitionEvent.StatusCode]
    STATUS_SUCCESS: SpeechRecognitionEvent.StatusCode
    STATUS_NO_SPEECH: SpeechRecognitionEvent.StatusCode
    STATUS_ABORTED: SpeechRecognitionEvent.StatusCode
    STATUS_AUDIO_CAPTURE: SpeechRecognitionEvent.StatusCode
    STATUS_NETWORK: SpeechRecognitionEvent.StatusCode
    STATUS_NOT_ALLOWED: SpeechRecognitionEvent.StatusCode
    STATUS_SERVICE_NOT_ALLOWED: SpeechRecognitionEvent.StatusCode
    STATUS_BAD_GRAMMAR: SpeechRecognitionEvent.StatusCode
    STATUS_LANGUAGE_NOT_SUPPORTED: SpeechRecognitionEvent.StatusCode
    class EndpointerEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        START_OF_SPEECH: _ClassVar[SpeechRecognitionEvent.EndpointerEventType]
        END_OF_SPEECH: _ClassVar[SpeechRecognitionEvent.EndpointerEventType]
        END_OF_AUDIO: _ClassVar[SpeechRecognitionEvent.EndpointerEventType]
        END_OF_UTTERANCE: _ClassVar[SpeechRecognitionEvent.EndpointerEventType]
    START_OF_SPEECH: SpeechRecognitionEvent.EndpointerEventType
    END_OF_SPEECH: SpeechRecognitionEvent.EndpointerEventType
    END_OF_AUDIO: SpeechRecognitionEvent.EndpointerEventType
    END_OF_UTTERANCE: SpeechRecognitionEvent.EndpointerEventType
    STATUS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    status: SpeechRecognitionEvent.StatusCode
    result: _containers.RepeatedCompositeFieldContainer[SpeechRecognitionResult]
    endpoint: SpeechRecognitionEvent.EndpointerEventType
    def __init__(self, status: _Optional[_Union[SpeechRecognitionEvent.StatusCode, str]] = ..., result: _Optional[_Iterable[_Union[SpeechRecognitionResult, _Mapping]]] = ..., endpoint: _Optional[_Union[SpeechRecognitionEvent.EndpointerEventType, str]] = ...) -> None: ...

class SpeechRecognitionResult(_message.Message):
    __slots__ = ("alternative", "final", "stability")
    ALTERNATIVE_FIELD_NUMBER: _ClassVar[int]
    FINAL_FIELD_NUMBER: _ClassVar[int]
    STABILITY_FIELD_NUMBER: _ClassVar[int]
    alternative: _containers.RepeatedCompositeFieldContainer[SpeechRecognitionAlternative]
    final: bool
    stability: float
    def __init__(self, alternative: _Optional[_Iterable[_Union[SpeechRecognitionAlternative, _Mapping]]] = ..., final: bool = ..., stability: _Optional[float] = ...) -> None: ...

class SpeechRecognitionAlternative(_message.Message):
    __slots__ = ("transcript", "confidence")
    TRANSCRIPT_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    transcript: str
    confidence: float
    def __init__(self, transcript: _Optional[str] = ..., confidence: _Optional[float] = ...) -> None: ...
