import os
from dotenv import load_dotenv
from openai import AzureOpenAI

def test_openai_connection():
    load_dotenv()

    required_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_DEPLOYMENT_NAME",
        "OPENAI_API_VERSION"
    ]

    # 印出設定值（隱藏 API key）
    print("目前設定：")
    for var in required_vars:
        value = os.getenv(var)
        if var == "AZURE_OPENAI_API_KEY" and value:
            print(f"{var}: {'*' * len(value)}")
        else:
            print(f"{var}: {value}")

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"錯誤: 以下環境變數未配置: {', '.join(missing_vars)}")
        return

    print("\n正在嘗試初始化 Azure OpenAI 並進行測試...")
    try:
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        # 測試完整性檢查
        print("\n正在檢查 API 可用性...")
        response = client.chat.completions.create(
            model=os.getenv("AZURE_DEPLOYMENT_NAME"),
            messages=[
                {"role": "user", "content": "你好，這是一個測試訊息。"}
            ]
        )

        print("\nAzure OpenAI 回應:")
        print(response.choices[0].message.content)
        print("\nAzure OpenAI API 連接成功！")

    except Exception as e:
        print(f"\n連接 Azure OpenAI 失敗: {e}")
        print("\n常見原因：")
        print("1. Deployment 名稱不正確（需要完全匹配 Azure Portal 中的名稱）")
        print("2. Endpoint URL 格式不正確（應為 https://YOUR_RESOURCE_NAME.openai.azure.com/）")
        print("3. API 版本不支援（建議使用 2024-02-15-preview）")
        print("4. API Key 不正確")

if __name__ == "__main__":
    test_openai_connection()