#!/usr/bin/env python3
"""
AIseek 备份上传后校验
验证 OSS 上的备份文件是否有效
"""
import os
import sys
from typing import Optional


def get_oss_client():
    """创建阿里云 OSS 客户端"""
    try:
        import oss2
    except Exception as e:
        raise SystemExit(f"oss2_missing: {e}")
    
    endpoint = os.getenv("BACKUP_S3_ENDPOINT_URL", "")
    bucket_name = os.getenv("BACKUP_S3_BUCKET", "")
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    
    if not bucket_name:
        raise SystemExit("missing_BACKUP_S3_BUCKET")
    if not access_key or not secret_key:
        raise SystemExit("missing_credentials")
    
    auth = oss2.Auth(access_key, secret_key)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    return bucket


def get_latest_backup(bucket, prefix: str) -> Optional[dict]:
    """获取最新的备份文件"""
    prefix = str(prefix or "").strip().strip("/")
    if prefix:
        prefix = prefix + "/"
    else:
        prefix = ""
    
    result = bucket.list_objects(prefix=prefix, max_keys=1)
    
    if not result.object_list:
        return None
    
    latest = result.object_list[0]
    return {
        "key": latest.key,
        "size": latest.size,
        "last_modified": latest.last_modified,
        "etag": latest.etag
    }


def verify_backup(bucket, key: str) -> bool:
    """验证备份文件"""
    print(f"🔍 验证备份文件：{key}")
    
    # 1. 获取文件元数据
    try:
        meta = bucket.get_object_meta(key)
    except Exception as e:
        print(f"❌ 无法获取文件元数据：{e}")
        return False
    
    # 2. 校验大小 > 0
    if meta.content_length <= 0:
        print(f"❌ 备份文件大小为 {meta.content_length} 字节（无效）")
        return False
    
    print(f"✅ 文件大小：{meta.content_length:,} 字节")
    
    # 3. 校验可读性（尝试读取前 1KB）
    try:
        obj = bucket.get_object(key, byte_range=(0, 1023))
        _ = obj.read()
        print(f"✅ 文件可读")
    except Exception as e:
        print(f"❌ 文件读取失败：{e}")
        return False
    
    # 4. 校验元数据
    print(f"✅ Content-Type: {meta.content_type}")
    print(f"✅ ETag: {meta.etag}")
    print(f"✅ 最后修改时间：{meta.last_modified}")
    
    return True


def main():
    print("=== AIseek 备份上传后校验 ===\n")
    
    # 创建 OSS 客户端
    bucket = get_oss_client()
    
    # 获取最新备份
    prefix = os.getenv("BACKUP_S3_PREFIX", "aiseek-backups")
    latest = get_latest_backup(bucket, prefix)
    
    if not latest:
        print(f"❌ 未找到备份文件（prefix: {prefix}）")
        sys.exit(1)
    
    print(f"📦 找到最新备份:\n")
    print(f"   文件：{latest['key']}")
    print(f"   大小：{latest['size']:,} 字节")
    print(f"   时间：{latest['last_modified']}")
    print(f"   ETag: {latest['etag']}")
    print()
    
    # 验证备份
    if not verify_backup(bucket, latest['key']):
        print("\n❌ 备份校验失败")
        sys.exit(1)
    
    # 校验关联文件（.sha256, .manifest.txt 等）
    base_key = latest['key'][: -len(".tar.gz")]
    sidecars = [
        base_key + ".tar.gz.sha256",
        base_key + ".manifest.txt",
        base_key + ".filelist.txt",
    ]
    
    print(f"\n📋 校验关联文件:")
    for sidecar in sidecars:
        try:
            meta = bucket.get_object_meta(sidecar)
            print(f"   ✅ {sidecar} ({meta.content_length:,} 字节)")
        except Exception:
            print(f"   ⚠️  {sidecar} (不存在)")
    
    print("\n✅ 备份校验通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
