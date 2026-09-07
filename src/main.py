"""
main.py
-------
CLI entrypoint for SentinelGraph AI's preprocessing pipeline.

Run:
    python main.py
"""

from src.preprocessing.pipeline import PreprocessingPipeline, PipelineConfig


def main():
    config = PipelineConfig()
    pipeline = PreprocessingPipeline(config)
    summary = pipeline.run()
    print(summary)


if __name__ == "__main__":
    main()
