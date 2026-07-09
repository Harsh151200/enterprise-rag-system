from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence


@dataclass
class ETLContext:
    source_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceDocument:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedDocument:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExtractPlugin(ABC):
    @abstractmethod
    def extract(self, context: ETLContext) -> Iterable[SourceDocument]:
        """Read input data from a source."""


class TransformPlugin(ABC):
    @abstractmethod
    def transform(
        self, documents: Iterable[ProcessedDocument], context: ETLContext
    ) -> Iterable[ProcessedDocument]:
        """Convert extracted documents into load-ready records."""


class LoadPlugin(ABC):
    @abstractmethod
    def load(
        self, documents: Iterable[ProcessedDocument], context: ETLContext
    ) -> int:
        """Persist processed records and return loaded count."""


class ETLPluginContract(ABC):
    @property
    @abstractmethod
    def extractors(self) -> Sequence[ExtractPlugin]:
        """Extractor plugin set."""

    @property
    @abstractmethod
    def transformers(self) -> Sequence[TransformPlugin]:
        """Transformer plugin set."""

    @property
    @abstractmethod
    def loaders(self) -> Sequence[LoadPlugin]:
        """Loader plugin set."""

    def run(self, context: ETLContext) -> List[ProcessedDocument]:
        extracted: List[SourceDocument] = []
        for extractor in self.extractors:
            extracted.extend(extractor.extract(context))

        transformed: List[ProcessedDocument] = [
            ProcessedDocument(content=doc.content, metadata=dict(doc.metadata))
            for doc in extracted
        ]
        for transformer in self.transformers:
            transformed = list(transformer.transform(transformed, context))

        for loader in self.loaders:
            loader.load(transformed, context)

        return transformed
