from .activities import ActivitiesAPIEndPoint
from .catalogues import CataloguesAPIEndPoint
from .charts import FindingChartsAPIEndPoint
from .datasets import DatasetsAPIEndPoint, DataFilesAPIEndPoint
from .objects import ExoplanetsAPIEndPoint, ObjectsAPIEndPoint
from .observingruns import NightLogAPIEndPoint, ObservingRunsAPIEndPoint
from .observingsites import InstrumentsAPIEndPoint, ObservingSitesAPIEndPoint, TelescopesAPIEndPoint
from .profiles import PersonalProfileAPIEndPoint, ProfileAPIEndPoint, ProfileAPIKeyAPIEndPoint
from .satellites import SatellitesAPIEndPoint
from .standardstars import StandardStarsAPIEndPoint
from .telegrams import TelegramsATelAPIEndPoint

__all__ = ["ActivitiesAPIEndPoint",
           "CataloguesAPIEndPoint",
           "FindingChartsAPIEndPoint",
           "DatasetsAPIEndPoint",
           "DataFilesAPIEndPoint",
           "ExoplanetsAPIEndPoint",
           "ObjectsAPIEndPoint",
           "NightLogAPIEndPoint",
           "ObservingRunsAPIEndPoint",
           "InstrumentsAPIEndPoint",
           "ObservingSitesAPIEndPoint",
           "TelescopesAPIEndPoint",
           "PersonalProfileAPIEndPoint",
           "ProfileAPIEndPoint",
           "ProfileAPIKeyAPIEndPoint",
           "SatellitesAPIEndPoint",
           "StandardStarsAPIEndPoint",
           "TelegramsATelAPIEndPoint"]
