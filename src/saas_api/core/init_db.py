import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.saas_api.models.prompt import PromptTemplate

# Import raw prompts
from prompts.docCreatorPrompt import doc_creator_system_prompt, doc_creator_user_prompt
from prompts.fetchExamplePrompt import fetch_example_system_prompt, fetch_example_user_prompt
from prompts.filesAnalyzerPrompt import (
    default_analyzer_system_prompt,
    c_sharp_analyzer_system_prompt,
    java_analyzer_system_prompt,
    file_analyzer_user_prompt
)

logger = logging.getLogger(__name__)

async def seed_system_prompts(db: AsyncSession):
    """Seed the system default prompts into the database on startup if they don't exist."""
    default_prompts = {
        "doc_creator_system": doc_creator_system_prompt,
        "doc_creator_user": doc_creator_user_prompt.template,
        "fetch_example_system": fetch_example_system_prompt,
        "fetch_example_user": fetch_example_user_prompt.template,
        "default_analyzer_system": default_analyzer_system_prompt,
        "c_sharp_analyzer_system": c_sharp_analyzer_system_prompt,
        "java_analyzer_system": java_analyzer_system_prompt,
        "file_analyzer_user": file_analyzer_user_prompt.template,
    }

    for name, content in default_prompts.items():
        result = await db.execute(
            select(PromptTemplate).where(
                PromptTemplate.name == name,
                PromptTemplate.is_system_default == True,
                PromptTemplate.team_id == None
            )
        )
        existing = result.scalars().first()
        
        if not existing:
            new_prompt = PromptTemplate(
                name=name,
                content=content,
                is_system_default=True,
                team_id=None
            )
            db.add(new_prompt)
            logger.info(f"Seeded System Prompt: {name}")
        else:
            # Overwrite system prompt content to ensure codebase updates are synced
            if existing.content != content:
                existing.content = content
                db.add(existing)
                logger.info(f"Updated System Prompt: {name}")

    await db.commit()
