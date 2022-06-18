
# model_name = "gpt2-medium"
model_name = "EleutherAI/gpt-neo-1.3B"
# model_name = "EleutherAI/gpt-neo-2.7B"
# model_name = "EleutherAI/gpt-neox-20b"
# model_name = "EleutherAI/gpt-j-6B"

cache_dir = None

default_kwargs = {
    "do_sample": True,
    "max_length": 70,
    "top_p": 0.90, # 0.7
    "top_k": 0,
    "temperature": 0.75,
}