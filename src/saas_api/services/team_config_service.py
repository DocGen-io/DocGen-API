from sqlalchemy.ext.asyncio import AsyncSession
from src.saas_api.models.team_config import TeamConfiguration
from src.saas_api.schemas.team_config import TeamConfigurationCreate, TeamConfigurationUpdate
from src.saas_api.repositories.team_config import team_config_repo
from src.saas_api.core.security import encrypt_value, decrypt_value

SENSITIVE_KEYS = {
    "aws_secret_access_key", 
    "gcs_service_account_json", 
    "azure_storage_key", 
    "openai_api_key",
    "anthropic_api_key"
}

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

    async def get_team_config(self, team_id: str) -> dict | None:
        db_config = await team_config_repo.get_by_team_id(self.db, team_id)
        if not db_config:
            return None
        return self._decrypt_payload(db_config.config_data)
        
    async def upsert_team_config(self, team_id: str, config_data: dict) -> dict:
        db_config = await team_config_repo.get_by_team_id(self.db, team_id)
        encrypted_data = self._encrypt_payload(config_data)
        
        if db_config:
            obj_in = TeamConfigurationUpdate(config_data=encrypted_data)
            updated = await team_config_repo.update_config(self.db, db_obj=db_config, obj_in=obj_in)
            return self._decrypt_payload(updated.config_data)
        else:
            obj_in = TeamConfigurationCreate(team_id=team_id, config_data=encrypted_data)
            created = await team_config_repo.create(self.db, obj_in=obj_in)
            return self._decrypt_payload(created.config_data)
