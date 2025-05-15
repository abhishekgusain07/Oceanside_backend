"""
Agent definitions for CrewAI.

This module contains specialized agents with clear roles, goals, and backstories
following the best practices from CrewAI documentation.
"""
from crewai import Agent
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.crewai_config import crewai_settings

# Get the default LLM based on configuration
def get_default_llm():
    """
    Creates the default language model based on configuration settings.
    
    Returns:
        A configured language model instance.
    """
    if crewai_settings.DEFAULT_LLM_PROVIDER == "google":
        return ChatGoogleGenerativeAI(
            model=crewai_settings.DEFAULT_LLM_MODEL,
            temperature=crewai_settings.DEFAULT_LLM_TEMPERATURE,
            # The API key is set in the environment by crewai_settings
        )
    else:  # Default to OpenAI
        return ChatOpenAI(
            temperature=crewai_settings.DEFAULT_LLM_TEMPERATURE,
            model=crewai_settings.DEFAULT_LLM_MODEL,
        )

# Initialize default LLM
default_llm = get_default_llm()

# Define specialized agents
def create_research_agent(llm=None):
    """
    Creates a specialized research agent for data gathering and analysis.
    
    Args:
        llm: Optional language model to use for this agent.
        
    Returns:
        Agent: A configured research agent.
    """
    return Agent(
        role="Research Specialist",
        goal="Gather comprehensive, accurate information from authoritative sources and synthesize it into structured insights",
        backstory=(
            "You are a meticulous researcher with a background in data science and information analysis. "
            "You have a talent for finding valuable information in diverse sources and organizing complex data "
            "into clear insights. Your analytical skills help you separate facts from opinions, identify trends, "
            "and produce high-quality research outputs."
        ),
        verbose=True,
        llm=llm or default_llm,
    )


def create_analyst_agent(llm=None):
    """
    Creates a specialized data analyst agent for interpreting research findings.
    
    Args:
        llm: Optional language model to use for this agent.
        
    Returns:
        Agent: A configured analyst agent.
    """
    return Agent(
        role="Data Insights Analyst",
        goal="Transform raw research into actionable insights by identifying patterns, opportunities, and implications",
        backstory=(
            "With 15+ years of experience in data analytics across multiple industries, "
            "you excel at finding meaningful signals in data noise. You have a proven track record "
            "of converting complex information into strategic recommendations. You're known for your "
            "ability to ask the right questions and think critically about assumptions in the data."
        ),
        verbose=True,
        llm=llm or default_llm,
    )


def create_writer_agent(llm=None):
    """
    Creates a specialized content writer agent for creating polished outputs.
    
    Args:
        llm: Optional language model to use for this agent.
        
    Returns:
        Agent: A configured writer agent.
    """
    return Agent(
        role="Content Specialist",
        goal="Transform complex insights into clear, engaging, and professional content tailored to the target audience",
        backstory=(
            "You are an experienced writer with expertise in technical and business communication. "
            "You've spent years crafting reports, articles, and presentations that explain complex topics "
            "in accessible ways. You have a keen eye for structure, clarity, and audience needs. "
            "You believe that good communication balances depth with accessibility."
        ),
        verbose=True,
        llm=llm or default_llm,
    ) 