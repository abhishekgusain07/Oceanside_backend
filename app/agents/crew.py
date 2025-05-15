"""
Crew definition for orchestrating agents and tasks.

This module contains the crew setup and orchestration logic for running
agent-based workflows following the best practices from CrewAI documentation.
"""
from crewai import Crew
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.crewai_config import crewai_settings
from app.agents.agents import (
    create_research_agent,
    create_analyst_agent,
    create_writer_agent,
    get_default_llm
)
from app.agents.tasks import (
    create_research_task,
    create_analysis_task,
    create_content_task
)


class ResearchCrewFactory:
    """
    Factory class for creating and configuring research crews.
    
    This class provides methods to create a standard research crew with
    customizable parameters for topic, content type, and audience.
    """
    
    def __init__(self, model_name=None, temperature=None, provider=None):
        """
        Initialize the factory with model configuration.
        
        Args:
            model_name: The model to use.
            temperature: The temperature setting for the model.
            provider: The model provider (google/openai).
        """
        # Determine provider
        self.provider = provider or crewai_settings.DEFAULT_LLM_PROVIDER
        
        # Initialize the appropriate LLM
        if model_name or temperature or provider:
            if self.provider == "google":
                self.llm = ChatGoogleGenerativeAI(
                    model=model_name or crewai_settings.DEFAULT_LLM_MODEL,
                    temperature=temperature or crewai_settings.DEFAULT_LLM_TEMPERATURE,
                    # The API key is set in the environment by crewai_settings
                )
            else:  # Default to OpenAI
                self.llm = ChatOpenAI(
                    temperature=temperature or crewai_settings.DEFAULT_LLM_TEMPERATURE,
                    model=model_name or crewai_settings.DEFAULT_LLM_MODEL,
                )
        else:
            # Use the default LLM
            self.llm = get_default_llm()
    
    def create_crew(self, topic, content_type="report", audience="professionals"):
        """
        Create a complete research crew with agents and tasks.
        
        Args:
            topic: The research topic for the crew to investigate.
            content_type: The type of content to produce (report, article, etc.).
            audience: The target audience for the content.
            
        Returns:
            Crew: A configured crew ready to be run.
        """
        # Create specialized agents
        research_agent = create_research_agent(self.llm)
        analyst_agent = create_analyst_agent(self.llm)
        writer_agent = create_writer_agent(self.llm)
        
        # Create sequential tasks
        research_task = create_research_task(research_agent, topic)
        analysis_task = create_analysis_task(
            analyst_agent, 
            research_task
        )
        content_task = create_content_task(
            writer_agent, 
            analysis_task, 
            content_type=content_type, 
            audience=audience
        )
        
        # Create and return the crew
        crew = Crew(
            agents=[research_agent, analyst_agent, writer_agent],
            tasks=[research_task, analysis_task, content_task],
            verbose=True,
            process=self._get_process()
        )
        
        return crew
    
    def _get_process(self):
        """
        Define the process for task execution.
        
        Returns:
            str: The process type for the crew.
        """
        # Using sequential process as default
        return "sequential"


async def run_research_crew(topic, content_type="report", audience="professionals", model=None, provider=None):
    """
    Asynchronous function to run a research crew and return the results.
    
    Args:
        topic: The research topic.
        content_type: The type of content to produce.
        audience: The target audience for the content.
        model: The model to use.
        provider: The model provider (google/openai).
        
    Returns:
        str: The result from the crew execution.
    """
    factory = ResearchCrewFactory(model_name=model, provider=provider)
    crew = factory.create_crew(topic, content_type, audience)
    
    # Run the crew and get the result
    result = crew.kickoff()
    
    return result 