from api.services.team_config_service import _deep_merge
from api.core.default_config import DEFAULT_TEAM_CONFIG
import yaml

merged = _deep_merge(DEFAULT_TEAM_CONFIG, {})
print(yaml.safe_dump(merged))
