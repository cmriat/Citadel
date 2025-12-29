/**
 * 验证API
 *
 * 提供路径验证和配置验证功能
 */

import api from './index'

// ============ 类型定义 ============

export interface PathValidationResult {
  valid: boolean
  exists: boolean
  is_dir: boolean
  is_file: boolean
  is_writable: boolean
  message: string
}

export interface BosPathValidationResult {
  valid: boolean
  format_ok: boolean
  message: string
}

export interface ValidationError {
  field: string
  message: string
}

export interface ConfigValidationResult {
  valid: boolean
  errors: ValidationError[]
}

export type ConfigType = 'download' | 'convert' | 'upload'

// ============ API函数 ============

/**
 * 验证本地路径
 */
export async function validateLocalPath(
  path: string,
  checkWritable: boolean = false
): Promise<PathValidationResult> {
  return api.post('/validate/local-path', {
    path,
    check_writable: checkWritable
  })
}

/**
 * 验证BOS路径
 */
export async function validateBosPath(path: string): Promise<BosPathValidationResult> {
  return api.post('/validate/bos-path', { path })
}

/**
 * 验证配置
 */
export async function validateConfig(
  configType: ConfigType,
  config: Record<string, unknown>
): Promise<ConfigValidationResult> {
  return api.post('/validate/config', {
    config_type: configType,
    config
  })
}

/**
 * 快速检查路径（GET方法）
 */
export async function checkPathQuick(path: string): Promise<{
  valid: boolean
  exists: boolean
  is_dir: boolean
  message: string
}> {
  return api.get('/validate/check-path', {
    params: { path }
  })
}

// ============ 辅助函数 ============

/**
 * 验证参数范围
 */
export function validateRange(value: number, min: number, max: number): boolean {
  return typeof value === 'number' && value >= min && value <= max
}

/**
 * 验证并发数 (1-20)
 */
export function validateConcurrency(value: number): boolean {
  return validateRange(value, 1, 20)
}

/**
 * 验证帧率 (1-120)
 */
export function validateFps(value: number): boolean {
  return validateRange(value, 1, 120)
}

/**
 * 验证并行任务数 (1-16)
 */
export function validateParallelJobs(value: number): boolean {
  return validateRange(value, 1, 16)
}

/**
 * 验证路径非空
 */
export function validatePathNotEmpty(path: string): boolean {
  return typeof path === 'string' && path.trim().length > 0
}
