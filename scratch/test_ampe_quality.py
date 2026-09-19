import asyncio
from app.services.prompt_builder import PromptBuilder
from app.services.prompt_analysis_service import PromptAnalysisService
from app.services.llm.base import BaseLLMProvider
from app.api.v1.deps import get_llm_provider

async def test():
    builder = PromptBuilder()
    llm = get_llm_provider()
    analyzer = PromptAnalysisService(llm_provider=llm)

    test_prompt = "Write a blog post about artificial intelligence in healthcare"
    print(f"\n==========================================")
    print(f"RAW PROMPT: {test_prompt}")
    print(f"==========================================")

    # 1. Build messages using upgraded AMPE
    messages = builder.build_adaptive_messages(raw_prompt=test_prompt)
    
    # 2. Generate enhanced prompt via LLM
    print("Generating enhanced prompt via LLM...")
    res = await llm.optimize_prompt(
        prompt=messages["user"],
        system=messages["system"],
        template_id="adaptive",
        max_tokens=4096,
    )
    enhanced_prompt = res.optimized_prompt.strip()
    print("\n--- ENHANCED PROMPT FULL ---")
    print(enhanced_prompt)

    # 3. Analyze enhanced prompt across the 6 dimensions
    print("\nAnalyzing quality across the 6 dimensions...")
    analysis = await analyzer.analyze(enhanced_prompt)
    print(f"\nOVERALL SCORE: {analysis['overall_score']} / 100 (Grade: {analysis['grade']})")
    print(f"Summary: {analysis.get('summary', '')}")
    print("\nDimension Breakdown:")
    for dim_name, data in analysis["dimensions"].items():
        print(f"  • {dim_name.upper()}: {data['score']}/100 (Weight: {data.get('weight', 0)}%)")

if __name__ == "__main__":
    asyncio.run(test())
