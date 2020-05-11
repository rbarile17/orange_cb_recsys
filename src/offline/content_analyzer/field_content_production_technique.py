from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Tuple, Dict

import numpy as np

from src.offline.content_analyzer.information_processor import InformationProcessor
from src.offline.memory_interfaces.text_interface import IndexInterface
from src.offline.content_analyzer.content_representation.content_field \
    import EmbeddingField, FeaturesBagField, FieldRepresentation, GraphField
from src.offline.raw_data_extractor.raw_information_source import RawInformationSource
from src.offline.utils.id_merger import id_merger


class FieldContentProductionTechnique(ABC):
    """
    Abstract class that generalize the technique to use for producing the semantic description
    of a content's field's representation
    """

    def __init__(self):
        pass


class CollectionBasedTechnique(FieldContentProductionTechnique):
    def __init__(self):
        super().__init__()
        self.__need_refactor: Dict[Tuple[str, str], List[InformationProcessor]] = {}

    def append_field_need_refactor(self, field_name: str, pipeline_id, processor_list: List[InformationProcessor]):
        self.__need_refactor[(field_name, pipeline_id)] = processor_list

    def get_need_refactor(self):
        return self.__need_refactor

    @abstractmethod
    def produce_content(self, field_representation_name: str, content_id: str,
                        field_name: str, pipeline_id: str) -> FieldRepresentation:
        pass

    @abstractmethod
    def dataset_refactor(self, information_source: RawInformationSource, id_field_names):
        pass


class SingleContentTechnique(FieldContentProductionTechnique):
    @abstractmethod
    def produce_content(self, field_representation_name: str, field_data: str) -> FieldRepresentation:
        """
        Given data of certain field it returns a complex representation's instance of the field.
        Args:
            field_representation_name: name of the field representation object that will be created
            field_data: input for the complex representation production

        Returns:
            FieldRepresentation: an instance of FieldRepresentation,
                 the particular type of representation depends from the technique
        """


class FieldToGraph(SingleContentTechnique):
    """
    Abstract class that generalize techniques
    that uses ontologies or LOD for producing the semantic description
    """

    @abstractmethod
    def produce_content(self, field_representation_name: str, **kwargs) -> GraphField:
        pass


class TfIdfTechnique(CollectionBasedTechnique):
    """
    Class that produce a Bag of words with tf-idf metric
    Args:

    """

    def __init__(self):
        super().__init__()
        self.__index = IndexInterface('./frequency-index')

    def produce_content(self, field_representation_name: str, **kwargs) -> FeaturesBagField:
        return FeaturesBagField(field_representation_name, self.__index.get_tf_idf(kwargs["field_name"], kwargs["item_id"]))

    def dataset_refactor(self, information_source: RawInformationSource, id_field_names: str):
        if len(self.get_need_refactor().keys()) != 0:
            self.__index = IndexInterface('./frequency-index')
            self.__index.init_writing()
            for raw_content in information_source:
                self.__index.new_content()
                id_values = []

                for name in id_field_names:
                    id_values.append(raw_content[name])

                self.__index.new_field("content_id", id_merger(id_values))

                for field_pipeline_name in self.get_need_refactor().keys():
                    preprocessor_list = self.get_need_refactor()[field_pipeline_name]
                    processed_field_data = raw_content[field_pipeline_name]
                    for preprocessor in preprocessor_list:
                        processed_field_data = preprocessor.process(processed_field_data)
                    self.__index.new_field(field_pipeline_name, processed_field_data)
                self.__index.serialize_content()

            self.__index.stop_writing()


class EntityLinking(SingleContentTechnique):
    """
    Abstract class that generalize implementations
    that uses entity linking for producing the semantic description
    """

    @abstractmethod
    def produce_content(self, field_representation_name: str, **kwargs) -> FeaturesBagField:
        pass


class Granularity(Enum):
    """
    Enumeration whose elements are the possible units
    respect to which combine for generating an embedding.
    """
    WORD = 1
    SENTENCE = 2
    DOC = 3


class CombiningTechnique(ABC):
    """
    Class that generalizes the modality in which previously learned embeddings will be
    combined to produce a semantic description.
    """

    def __init__(self):
        pass

    @abstractmethod
    def combine(self, embedding_matrix: np.ndarray):
        """
        Combine, in a way specified in the implementations,
        the row of the input matrix

        Args:
            embedding_matrix: matrix whose rows will be combined

        Returns:

        """
        pass


class EmbeddingSource(ABC):
    """
    General class whose purpose is to
    store the loaded pre-trained embeddings model and
    extract from it specified words

    Args:
        self.__model: embeddings model loaded from source
    """

    def __init__(self):
        self.__model = None

    def load(self, text: str) -> np.ndarray:
        """
        Function that extract from the embeddings model
        the vectors of thw words contained in text

        Args:
            text (str): contains words of which vectors will be extracted

        Returns:
            np.ndarray: bi-dimensional numpy vector,
                each row is a term vector
        """
        embedding_matrix = np.ndarray(shape=(len(text), self.get_vector_size()))

        for i, word in enumerate(text):
            try:
                embedding_matrix[i, :] = self.__model[word]
            except:
                pass
        return embedding_matrix

    def set_model(self, model):
        self.__model = model

    def get_vector_size(self) -> int:
        return self.__model.vector_size


class SentenceDetectionTechnique(ABC):
    """
    Abstract class that generalizes implementation of
    techniques used to divide a text in sentences
    """

    def __init__(self):
        pass

    @abstractmethod
    def detect_sentences(self, text: str) -> List[str]:
        """
        Divide the input text in a list of sentences

        Args:
            text (str): text that will be divided

        Returns:
            List<str>: list of sentences
        """
        pass


class EmbeddingTechnique(SingleContentTechnique):
    """
    Class that can be used to combine different embeddings coming to various sources
    in order to produce the semantic description.

    Args:
        combining_technique (CombiningTechnique): The technique that will be used
        for combining the embeddings.
        embedding_source (EmbeddingSource):
            Source from which extract the embeddings vectors for the words in field_data.
        sentence_detection (SentenceDetectionTechnique): technique that wil lbe use to divide
            the text in sentences if the granularity specified is SENTENCE
        granularity (Granularity): It can assume three values,
            depending on whether framework user want
            to combine relatively to words, phrases or documents.
    """

    def __init__(self, combining_technique: CombiningTechnique,
                 embedding_source: EmbeddingSource,
                 **kwargs):
        super().__init__()
        self.__combining_technique: CombiningTechnique = combining_technique
        self.__embedding_source: EmbeddingSource = embedding_source

        if "sentence_detection" in kwargs.keys():
            self.__sentence_detection: SentenceDetectionTechnique = kwargs["sentence_detection"]
        if "granularity" in kwargs.keys():
            self.__granularity: Granularity = kwargs["granularity"]

    def produce_content(self, field_representation_name: str, **kwargs) -> EmbeddingField:
        """
        Method that builds the semantic content starting from the embeddings contained in
        field_data.
        Args:
            field_representation_name:
            field_data: The terms whose embeddings will be combined.

        Returns:
            np.ndarray:
                mono-dimensional array for DOC embedding
                bi-dimensional array for SENTENCE and WORD embedding
        """

        if self.__granularity == 1:
            doc_matrix = self.__embedding_source.load(kwargs["field_data"])
            return EmbeddingField(field_representation_name, doc_matrix)
        if self.__granularity == 2:
            sentences = self.__sentence_detection.detect_sentences(kwargs["field_data"])
            sentences_embeddings = np.ndarray(shape=(len(sentences),
                                                     self.__embedding_source.get_vector_size()))
            for i, sentence in enumerate(sentences):
                sentence_matrix = self.__embedding_source.load(sentence)
                sentences_embeddings[i, :] = self.__combining_technique.combine(sentence_matrix)

            return EmbeddingField(field_representation_name, sentences_embeddings)
        if self.__granularity == 3:
            doc_matrix = self.__embedding_source.load(kwargs["field_data"])
            return EmbeddingField(field_representation_name, self.__combining_technique.combine(doc_matrix))
