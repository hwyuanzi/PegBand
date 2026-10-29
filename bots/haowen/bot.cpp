// Haowen / Aegis: standalone PegBand tournament entry, C++17.
#include <cctype>
#include <iostream>
#include <string>
#include "bands.h"
#include "pegs.h"

namespace json {
// The referee sends only integer scalars, strings, and arrays. Accept whitespace
// as well as its normal compact JSON without relying on third-party libraries.
size_t value(const std::string& s,const std::string& key) {
    size_t p=s.find('"'+key+'"');
    if(p==std::string::npos)return p;
    p=s.find(':',p+key.size()+2);
    if(p==std::string::npos)return p;
    do{++p;}while(p<s.size()&&std::isspace(static_cast<unsigned char>(s[p])));
    return p;
}
int integer(const std::string& s,const std::string& key,int fallback=0) {
    size_t p=value(s,key);return p==std::string::npos?fallback:std::atoi(s.c_str()+p);
}
std::string string(const std::string&s,const std::string&key) {
    size_t p=value(s,key);if(p==std::string::npos||s[p]!='"')return "";
    size_t e=s.find('"',p+1);return s.substr(p+1,e-p-1);
}
std::vector<int> array(const std::string&s,const std::string&key) {
    std::vector<int> out;size_t p=value(s,key);
    if(p==std::string::npos||s[p]!='[')return out;
    for(++p;p<s.size()&&s[p]!=']';){
        if(s[p]=='-'||std::isdigit(static_cast<unsigned char>(s[p]))){char* e;out.push_back(static_cast<int>(std::strtol(s.c_str()+p,&e,10)));p=e-s.c_str();}
        else ++p;
    }
    return out;
}
}

struct Bot {
    int n=10,k=5,r=5;
    double remaining=120;
    std::vector<std::vector<int>> plan;
    size_t next_band=0;
    void start(const std::string& line) {
        n=json::integer(line,"N",10);k=json::integer(line,"pegs",5);r=json::integer(line,"bands",5);
        remaining=json::integer(line,"clock",120);plan.clear();next_band=0;
    }
    int peg(const std::string&line) {
        auto a=json::array(line,"your_pegs"),b=json::array(line,"their_pegs");
        int left=std::max(1,k-static_cast<int>(a.size()));
        double budget=std::min(4.0,std::max(.05,(remaining-8.0)/left*.80));
        if(const char* e=std::getenv("PEGBAND_SECONDS"))budget=std::min(budget,std::max(.01,std::atof(e)));
        auto begin=std::chrono::steady_clock::now();
        placement::Search search(n,k,r,budget);
        int q=search.choose(a,b);
        remaining-=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count()+.003;
        return q;
    }
    std::vector<int> band(const std::string&line) {
        auto a=json::array(line,"your_pegs"),b=json::array(line,"their_pegs");
        if(plan.empty()) {
            auto begin=std::chrono::steady_clock::now();
            auto result=pegband::solve_bands(n,a,b,r,std::max(.01,std::min(5.0,remaining-2.0)));
            plan=std::move(result.bands);
            remaining-=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count()+.003;
        }
        if(next_band<plan.size())return plan[next_band++];
        return a.empty()?std::vector<int>{}:std::vector<int>{a.front()};
    }
};
int main(){
    std::ios::sync_with_stdio(false);std::cin.tie(nullptr);
    Bot bot;std::string line;
    while(std::getline(std::cin,line)) {
        if(line.empty())continue;
        auto type=json::string(line,"type");
        if(type=="start"){bot.start(line);std::cout<<"{\"ready\":true}\n"<<std::flush;}
        else if(type=="peg"){int q=bot.peg(line);std::cout<<"{\"peg\":"<<q<<"}\n"<<std::flush;}
        else if(type=="band"){
            auto band=bot.band(line);std::cout<<"{\"band\":[";
            for(size_t i=0;i<band.size();i++){if(i)std::cout<<',';std::cout<<band[i];}
            std::cout<<"]}\n"<<std::flush;
        }else std::cout<<"{}\n"<<std::flush;
    }
}
