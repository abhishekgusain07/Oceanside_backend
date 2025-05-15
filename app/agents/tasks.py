"""
Task definitions for CrewAI.

This module contains specialized tasks with clear descriptions, expected outputs, 
and other properties following the best practices from CrewAI documentation.
"""
from crewai import Task

def create_research_task(agent, topic):
    """
    Creates a research task for the research agent.
    
    Args:
        agent: The agent to assign the task to.
        topic: The topic to research.
        
    Returns:
        Task: A configured research task.
    """
    return Task(
        description=f"""
        Research the topic of "{topic}" thoroughly. Your research should:
        1. Gather information from credible sources
        2. Identify key facts, statistics, and expert opinions
        3. Organize the information in a structured format
        4. Highlight major trends, challenges, and opportunities
        5. Include relevant context that helps understand the topic

        Focus on being comprehensive but prioritize quality and relevance of information.
        """,
        expected_output=f"""
        A structured research report on "{topic}" containing:
        - Executive summary of key findings (3-5 bullet points)
        - Comprehensive data and information organized by subtopics
        - Citations or references to sources
        - Identified knowledge gaps or areas requiring further research
        
        The report should be factual, well-organized, and ready for analysis.
        """,
        agent=agent,
        context=[
            f"The research is about: {topic}",
            "This research will be used for further analysis and content creation.",
            "Separate facts from opinions and speculation in your reporting."
        ]
    )


def create_analysis_task(agent, research_task):
    """
    Creates an analysis task for the analyst agent.
    
    Args:
        agent: The agent to assign the task to.
        research_task: The preceding research task that provides input for analysis.
        
    Returns:
        Task: A configured analysis task.
    """
    return Task(
        description="""
        Analyze the research findings and extract meaningful insights. Your analysis should:
        1. Identify key patterns, trends, and correlations in the data
        2. Evaluate the significance and implications of the findings
        3. Compare and contrast different perspectives or data points
        4. Develop actionable insights based on the research
        5. Prioritize insights based on relevance and potential impact
        
        Focus on depth of understanding rather than just summarizing the research.
        """,
        expected_output="""
        An analytical report containing:
        - 3-5 key insights derived from the research
        - Supporting evidence for each insight
        - Implications and potential applications of these insights
        - Recommendations for further action or investigation
        - Visual representation of data patterns (described in text format)
        
        The analysis should be insightful, evidence-based, and actionable.
        """,
        agent=agent,
        context=[
            "This analysis builds upon the previous research task.",
            "Focus on extracting non-obvious insights from the data.",
            "Consider multiple interpretations of the findings."
        ],
        async_execution=False,
        human_input=False
    )


def create_content_task(agent, analysis_task, content_type="report", audience="professionals"):
    """
    Creates a content creation task for the writer agent.
    
    Args:
        agent: The agent to assign the task to.
        analysis_task: The preceding analysis task that provides input for content creation.
        content_type: The type of content to create (report, article, etc.).
        audience: The target audience for the content.
        
    Returns:
        Task: A configured content creation task.
    """
    return Task(
        description=f"""
        Create a {content_type} based on the research and analysis provided. Your content should:
        1. Present the insights in a clear, engaging, and coherent narrative
        2. Structure the content appropriately for a {content_type} format
        3. Use language and terminology suitable for {audience}
        4. Include an executive summary and key takeaways
        5. Maintain accuracy while making the content accessible
        
        Focus on clarity, engagement, and professionalism in your writing.
        """,
        expected_output=f"""
        A complete {content_type} containing:
        - Compelling title and introduction
        - Well-structured presentation of the insights and findings
        - Clear explanations of complex concepts
        - Conclusion summarizing key points and potential next steps
        - Professional tone appropriate for {audience}
        
        The content should be ready for distribution to the target audience.
        """,
        agent=agent,
        context=[
            f"You are creating a {content_type} for {audience}.",
            "The content should accurately reflect the research and analysis.",
            "Balance depth with accessibility in your communication."
        ],
        async_execution=False,
        human_input=False
    ) 