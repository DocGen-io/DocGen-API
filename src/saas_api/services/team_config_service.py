import copy
from sqlalchemy.ext.asyncio import AsyncSession
from src.saas_api.models.team_config import TeamConfiguration
from src.saas_api.schemas.team_config import TeamConfigurationCreate, TeamConfigurationUpdate
from src.saas_api.repositories.team_config import team_config_repo
from src.saas_api.core.security import encrypt_value, decrypt_value
from src.saas_api.core.default_config import DEFAULT_TEAM_CONFIG

SENSITIVE_KEYS = {
    "aws_secret_access_key", 
    "gcs_service_account_json", 
    "azure_storage_key", 
    "openai_api_key",
    "anthropic_api_key"
}

def _deep_merge(dict1: dict, dict2: dict) -> dict:
    """Deep merge dict2 into dict1."""
    result = copy.deepcopy(dict1)
    for key, value in dict2.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result

class TeamConfigService:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    def _encrypt_payload(self, config_data: dict) -> dict:
        encrypted = config_data.copy()
        for k, v in encrypted.items():
            if k in SENSITIVE_KEYS and isinstance(v, str):
                encrypted[k] = encrypt_value(v)
        return encrypted
        
    def _decrypt_payload(self, config_data: dict) -> dict:
        decrypted = config_data.copy()
        for k, v in decrypted.items():
            if k in SENSITIVE_KEYS and isinstance(v, str):
                decrypted[k] = decrypt_value(v)
        return decrypted

    async def get_team_config(self, team_id: str) -> dict:
        db_config = await team_config_repo.get_by_team_id(self.db, team_id)
        if not db_config:
            return copy.deepcopy(DEFAULT_TEAM_CONFIG)
        
        decrypted_db = self._decrypt_payload(db_config.config_data)
        return _deep_merge(DEFAULT_TEAM_CONFIG, decrypted_db)
        
    async def upsert_team_config(self, team_id: str, incoming_config: dict) -> dict:
        # Fetch existing to merge onto it, to avoid wiping keys on partial updates
        db_config = await team_config_repo.get_by_team_id(self.db, team_id)
        
        if db_config:
            existing_decrypted = self._decrypt_payload(db_config.config_data)
            merged_config = _deep_merge(existing_decrypted, incoming_config)
            encrypted_data = self._encrypt_payload(merged_config)
            
            obj_in = TeamConfigurationUpdate(config_data=encrypted_data)
            updated = await team_config_repo.update_config(self.db, db_obj=db_config, obj_in=obj_in)
            
            # Return the synthesized view against DEFAULT_TEAM_CONFIG
            return _deep_merge(DEFAULT_TEAM_CONFIG, self._decrypt_payload(updated.config_data))
        else:
            encrypted_data = self._encrypt_payload(incoming_config)
            obj_in = TeamConfigurationCreate(team_id=team_id, config_data=encrypted_data)
            created = await team_config_repo.create(self.db, obj_in=obj_in)
            
            # Return the synthesized view against DEFAULT_TEAM_CONFIG
            return _deep_merge(DEFAULT_TEAM_CONFIG, self._decrypt_payload(created.config_data))

