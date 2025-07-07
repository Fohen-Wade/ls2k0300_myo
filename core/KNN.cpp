#include <vector>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <queue>
#include <limits>
#include <ctime>
#include <random>
#include <cstring> // 用于memcpy

class KNNTrainer {
public:
    KNNTrainer(int k = 5, int max_samples = 1500) 
        : k(k), max_samples(max_samples), trained(false) {}
    
    void load_data(const std::string& base_path) {
        samples.clear();
        labels.clear();
        squared_norms.clear();
        
        for (int gesture_id = 0; gesture_id < 10; ++gesture_id) {
            std::string filename = base_path + "/vals" + std::to_string(gesture_id) + ".dat";
            std::ifstream file(filename, std::ios::binary);
            
            if (!file) {
                std::cerr << "警告: 未找到数据文件: " << filename << std::endl;
                continue;
            }
            
            // 读取二进制数据
            file.seekg(0, std::ios::end);
            size_t size = file.tellg();
            if (size == 0) {
                std::cerr << "文件为空: " << filename << std::endl;
                continue;
            }
            file.seekg(0, std::ios::beg);
            
            // 计算样本数量
            size_t num_samples = size / (8 * sizeof(uint16_t));
            if (num_samples == 0) {
                std::cerr << "文件中没有有效样本: " << filename << std::endl;
                continue;
            }
            
            // 读取所有数据
            std::vector<uint16_t> data(8 * num_samples);
            file.read(reinterpret_cast<char*>(data.data()), static_cast<std::streamsize>(size));
            
            // 限制样本数量（最大1500）
            if (num_samples > max_samples) {
                // 使用高质量的随机选择
                std::vector<uint16_t> selected;
                selected.reserve(max_samples * 8);
                
                // 使用C++11随机数引擎
                std::random_device rd;
                std::mt19937 gen(rd());
                std::uniform_int_distribution<size_t> dis(0, num_samples - 1);
                
                // 随机选择1500个样本
                for (size_t i = 0; i < max_samples; ++i) {
                    size_t idx = dis(gen);
                    for (int j = 0; j < 8; ++j) {
                        selected.push_back(data[idx * 8 + j]);
                    }
                }
                data = std::move(selected);
                num_samples = max_samples;
            }
            
            // 添加样本和标签
            for (size_t i = 0; i < num_samples; ++i) {
                samples.push_back(std::vector<uint16_t>(data.begin() + i * 8, data.begin() + (i + 1) * 8));
                labels.push_back(gesture_id);
            }
            
            std::cout << "加载手势 " << gesture_id << " 的样本: " << num_samples << " 个" << std::endl;
        }
        
        if (!samples.empty()) {
            train(); // 预计算范数
            trained = true;
            std::cout << "总共加载 " << samples.size() << " 个样本用于分类" << std::endl;
        } else {
            std::cerr << "错误: 没有加载任何训练数据!" << std::endl;
        }
    }
    
    void train() {
        squared_norms.resize(samples.size());
        
        // 手动优化循环（无OpenMP）
        for (size_t i = 0; i < samples.size(); ++i) {
            const auto& sample = samples[i];
            double norm_sq = 0.0;
            
            // 手动循环展开（优化计算）
            for (int j = 0; j < 8; j++) {
                uint16_t val = sample[j];
                norm_sq += static_cast<double>(val) * val;
            }
            
            squared_norms[i] = norm_sq;
        }
    }
    
    std::pair<int, float> classify(const std::vector<uint16_t>& query) const {
        if (!trained || samples.empty()) {
            return {0, 0.0f};
        }
        
        // 计算查询向量范数平方
        double query_norm_sq = 0.0;
        for (uint16_t val : query) {
            query_norm_sq += static_cast<double>(val) * val;
        }
        
        // 使用优先队列存储前k个最近邻
        using DistIndex = std::pair<double, size_t>;
        auto comp = [](const DistIndex& a, const DistIndex& b) { 
            return a.first < b.first;
        };
        std::priority_queue<DistIndex, std::vector<DistIndex>, decltype(comp)> pq(comp);
        
        // 计算所有距离
        for (size_t i = 0; i < samples.size(); ++i) {
            const auto& sample = samples[i];
            double dot_product = 0.0;
            
            // 手动循环展开（优化点积计算）
            for (int j = 0; j < 8; j++) {
                dot_product += static_cast<double>(sample[j]) * query[j];
            }
            
            // 计算距离平方
            double dist_sq = squared_norms[i] + query_norm_sq - 2 * dot_product;
            
            // 添加到优先队列
            if (pq.size() < k) {
                pq.push({dist_sq, i});
            } else if (dist_sq < pq.top().first) {
                pq.pop();
                pq.push({dist_sq, i});
            }
        }
        
        // 统计类别投票
        std::vector<int> votes(10, 0);
        size_t count = pq.size();
        while (!pq.empty()) {
            size_t idx = pq.top().second;
            if (idx < labels.size()) { // 添加边界检查
                int label = labels[idx];
                if (label >= 0 && label < 10) { // 确保标签有效
                    votes[label]++;
                }
            }
            pq.pop();
        }
        
        // 找到最多票数的类别
        int prediction = 0;
        int max_votes = 0;
        for (int i = 0; i < 10; ++i) {
            if (votes[i] > max_votes) {
                max_votes = votes[i];
                prediction = i;
            }
        }
        
        float confidence = (count > 0) ? static_cast<float>(max_votes) / count : 0.0f;
        return {prediction, confidence};
    }
    
private:
    int k;
    int max_samples; // 每个手势最大样本数（设置为1500）
    bool trained;
    std::vector<std::vector<uint16_t>> samples;
    std::vector<int> labels;
    std::vector<double> squared_norms;
};

// Python接口函数
extern "C" {
    // 创建KNN分类器对象
    KNNTrainer* knn_create(int k, int max_samples) {
        return new KNNTrainer(k, max_samples);
    }
    
    // 加载训练数据
    void knn_load_data(KNNTrainer* classifier, const char* base_path) {
        classifier->load_data(base_path);
    }
    
    // 对EMG数据进行分类
    void knn_classify(KNNTrainer* classifier, const uint16_t* query, int* prediction, float* confidence) {
        // 将C数组转换为vector
        std::vector<uint16_t> q(query, query + 8);
        auto result = classifier->classify(q);
        *prediction = result.first;
        *confidence = result.second;
    }
    
    // 销毁KNN分类器对象
    void knn_destroy(KNNTrainer* classifier) {
        delete classifier;
    }
}