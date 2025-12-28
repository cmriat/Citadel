#!/usr/bin/env bash
################################################################################
# BOS数据下载脚本 - mc版本
# 功能：使用MinIO Client (mc) 从百度对象存储下载数据
# 特性：进度条、时间统计、可配置路径和并发数
################################################################################

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
BOS_ENDPOINT="https://s3.bj.bcebos.com"
BOS_ACCESS_KEY="ALTAKWzYq1SJf8JQ63fuuzVQSI"
BOS_SECRET_KEY="7654305587b24455bd534fa5ee210b11"
BOS_REGION="bj"

# 可配置参数（可通过命令行覆盖）
MC_PATH="${MC_PATH:-/home/maozan/mc}"  # mc可执行文件路径，可通过环境变量覆盖
BOS_SOURCE="srgdata/robot/raw_data/upload_test/1223_qz2_online_data_upload/quad_arm_task/"
LOCAL_DEST="/home/maozan/data/1223_qz2/"
CONCURRENCY=10  # mc推荐并发数：10

# 帮助信息
show_help() {
    cat << EOF
使用方法: $0 [选项]

选项:
    -m, --mc-path PATH      mc可执行文件路径 (默认: $MC_PATH)
    -s, --source PATH       BOS源路径 (默认: $BOS_SOURCE)
    -d, --dest PATH         本地目标路径 (默认: $LOCAL_DEST)
    -c, --concurrency NUM   并发数 (默认: $CONCURRENCY)
    -h, --help              显示此帮助信息

示例:
    # 使用默认配置
    $0

    # 自定义路径和并发数
    $0 --source bos/data/test/ --dest /tmp/download --concurrency 20

    # 指定mc路径
    $0 --mc-path /usr/local/bin/mc

    # 仅修改并发数
    $0 -c 10

EOF
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--mc-path)
            MC_PATH="$2"
            shift 2
            ;;
        -s|--source)
            BOS_SOURCE="$2"
            shift 2
            ;;
        -d|--dest)
            LOCAL_DEST="$2"
            shift 2
            ;;
        -c|--concurrency)
            CONCURRENCY="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}错误: 未知参数 '$1'${NC}"
            echo "使用 '$0 --help' 查看帮助信息"
            exit 1
            ;;
    esac
done

# 检查mc是否存在
if [ ! -f "$MC_PATH" ]; then
    echo -e "${RED}❌ 错误: 未找到mc命令于: $MC_PATH${NC}"
    echo "请确认mc路径正确，或通过以下方式指定："
    echo "  1. 命令行参数: $0 --mc-path /path/to/mc"
    echo "  2. 环境变量: export MC_PATH=/path/to/mc"
    echo ""
    echo "如需安装MinIO Client:"
    echo "  wget https://dl.min.io/client/mc/release/linux-amd64/mc"
    echo "  chmod +x mc"
    echo "  mv mc /home/maozan/mc  # 或其他路径"
    exit 1
fi

# 确保mc可执行
if [ ! -x "$MC_PATH" ]; then
    echo -e "${YELLOW}⚠️  mc文件不可执行，正在添加执行权限...${NC}"
    chmod +x "$MC_PATH"
fi

# 打印配置信息
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                     ${GREEN}BOS数据下载工具 - mc版本${NC}                           ${BLUE}║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📋 配置信息:${NC}"
echo -e "  mc路径:        $MC_PATH"
echo -e "  BOS Endpoint:  $BOS_ENDPOINT"
echo -e "  BOS Region:    $BOS_REGION"
echo -e "  源路径:        $BOS_SOURCE"
echo -e "  目标路径:      $LOCAL_DEST"
echo -e "  并发数:        $CONCURRENCY"
echo ""

# 配置mc alias (如果尚未配置)
echo -e "${YELLOW}🔧 配置mc客户端...${NC}"
"$MC_PATH" alias set bos "$BOS_ENDPOINT" "$BOS_ACCESS_KEY" "$BOS_SECRET_KEY" --api S3v4 &> /dev/null || true
echo -e "${GREEN}✅ mc配置完成${NC}"
echo ""

# 创建本地目录
mkdir -p "$LOCAL_DEST"

# 记录开始时间
START_TIME=$(date +%s)
START_TIME_STR=$(date '+%Y-%m-%d %H:%M:%S')

echo -e "${YELLOW}⏰ 开始时间: $START_TIME_STR${NC}"
echo -e "${YELLOW}▶️  开始下载...${NC}"
echo ""

# 执行下载
# mc mirror 自带进度显示，支持断点续传和并发
if "$MC_PATH" mirror \
    --overwrite \
    --preserve \
    --max-workers="$CONCURRENCY" \
    "bos/$BOS_SOURCE" \
    "$LOCAL_DEST"; then

    # 记录结束时间
    END_TIME=$(date +%s)
    END_TIME_STR=$(date '+%Y-%m-%d %H:%M:%S')
    DURATION=$((END_TIME - START_TIME))

    # 计算时长
    HOURS=$((DURATION / 3600))
    MINUTES=$(((DURATION % 3600) / 60))
    SECONDS=$((DURATION % 60))

    # 统计下载的文件
    if command -v tree &> /dev/null; then
        FILE_COUNT=$(tree -a "$LOCAL_DEST" | tail -1 | grep -oP '\d+(?= file)')
    else
        FILE_COUNT=$(find "$LOCAL_DEST" -type f | wc -l)
    fi

    # 计算下载大小
    if command -v du &> /dev/null; then
        DOWNLOAD_SIZE=$(du -sh "$LOCAL_DEST" | cut -f1)
    else
        DOWNLOAD_SIZE="未知"
    fi

    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}                          ${GREEN}下载完成统计${NC}                                   ${BLUE}║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}✅ 下载成功完成！${NC}"
    echo ""
    echo -e "${YELLOW}📊 统计信息:${NC}"
    echo -e "  开始时间:      $START_TIME_STR"
    echo -e "  结束时间:      $END_TIME_STR"

    if [ $HOURS -gt 0 ]; then
        echo -e "  总耗时:        ${HOURS}小时 ${MINUTES}分钟 ${SECONDS}秒"
    elif [ $MINUTES -gt 0 ]; then
        echo -e "  总耗时:        ${MINUTES}分钟 ${SECONDS}秒"
    else
        echo -e "  总耗时:        ${SECONDS}秒"
    fi

    echo -e "  文件数量:      $FILE_COUNT"
    echo -e "  下载大小:      $DOWNLOAD_SIZE"
    echo -e "  保存位置:      $LOCAL_DEST"

    # 计算平均速度
    if [ $DURATION -gt 0 ] && [ "$FILE_COUNT" != "0" ]; then
        AVG_FILES_PER_SEC=$(echo "scale=2; $FILE_COUNT / $DURATION" | bc -l)
        echo -e "  平均速度:      ${AVG_FILES_PER_SEC} 文件/秒"
    fi

    echo ""

else
    # 下载失败
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    echo -e "${RED}❌ 下载失败${NC}"
    echo -e "${YELLOW}已运行时间: ${DURATION}秒${NC}"
    echo ""
    echo -e "${YELLOW}💡 提示:${NC}"
    echo "  1. 检查网络连接"
    echo "  2. 验证BOS路径是否正确"
    echo "  3. 确认访问密钥配置正确"
    echo "  4. 重新运行此脚本可继续下载（支持断点续传）"
    echo ""
    exit 1
fi
