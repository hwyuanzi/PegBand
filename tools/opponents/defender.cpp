// Adversarial local sparring partner; not part of the submitted bot.
// Compile: c++ -std=c++17 -O2 tools/opponents/defender.cpp -o /tmp/pegband-defender
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <numeric>
#include <random>
#include <string>
#include <vector>
#include "../../bots/haowen/bands.h"

using namespace std;
struct P {int x,y;};
static int n,k,r;
static vector<P> samples;
static int cross(P a,P b,P c){return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);}
static P pt(int i){return {i%n,i/n};}
static bool segment(P p,P a,P b){return cross(a,b,p)==0 && p.x>=min(a.x,b.x)&&p.x<=max(a.x,b.x)&&p.y>=min(a.y,b.y)&&p.y<=max(a.y,b.y);}
static bool contains(P p, const vector<P>& s) {
    if(s.size()==1) return p.x==s[0].x&&p.y==s[0].y;
    if(s.size()==2) return segment(p,s[0],s[1]);
    return cross(s[0],s[1],p)>=0&&cross(s[1],s[2],p)>=0&&cross(s[2],s[0],p)>=0;
}
static bool hits(P p,const vector<P>& s){
    if(s.size()==1)return p.x==s[0].x&&p.y==s[0].y;
    int lx=n,ly=n,hx=-1,hy=-1;
    for(P q:s){lx=min(lx,q.x);ly=min(ly,q.y);hx=max(hx,q.x);hy=max(hy,q.y);}
    if(p.x<lx||p.x>hx||p.y<ly||p.y>hy)return false;
    if(s.size()==2){int z=2*cross(s[0],s[1],p),w=abs(s[1].x-s[0].x)+abs(s[1].y-s[0].y);return abs(z)<w;}
    for(int i=0;i<3;i++){P a=s[i],b=s[(i+1)%3];if(2*cross(a,b,p)<=-abs(b.x-a.x)-abs(b.y-a.y))return false;}
    return true;
}
using Bits=array<uint64_t,4>;
static void add(Bits& a,const Bits& b){for(int i=0;i<4;i++)a[i]|=b[i];}
static int size(const Bits& a){int v=0;for(auto x:a)v+=__builtin_popcountll(x);return v;}
struct Shape{vector<P> p;Bits cover;};
static Shape shape(vector<P> p,const vector<int>& enemy){
    if(p.size()==3){int z=cross(p[0],p[1],p[2]);if(z<0)swap(p[1],p[2]);if(z==0){sort(p.begin(),p.end(),[](P a,P b){return a.x!=b.x?a.x<b.x:a.y<b.y;});p={p.front(),p.back()};}}
    Shape s{p,{}};
    for(int q:enemy)if(contains(pt(q),p)){s.p.clear();return s;}
    for(int i=0;i<(int)samples.size();i++)if(hits(samples[i],p))s.cover[i/64]|=uint64_t(1)<<(i%64);
    return s;
}
static vector<Shape> shapes(const vector<int>& own,const vector<int>& enemy){
    vector<Shape> out;
    for(int a=0;a<(int)own.size();a++){
        out.push_back(shape({pt(own[a])},enemy));
        for(int b=0;b<a;b++){
            Shape s=shape({pt(own[a]),pt(own[b])},enemy);if(!s.p.empty())out.push_back(s);
            for(int c=0;c<b;c++){s=shape({pt(own[a]),pt(own[b]),pt(own[c])},enemy);if(!s.p.empty())out.push_back(s);}
        }
    }
    return out;
}
static int peg(const vector<int>& own,const vector<int>& enemy){
    vector<bool> taken(n*n,false);for(int i:own)taken[i]=true;for(int i:enemy)taken[i]=true;
    if(own.empty()&&k>=3){int c=(n/2)*n+n/2;if(!taken[c])return c;}
    vector<Shape> os=shapes(own,enemy),es=shapes(enemy,own);
    Bits base{};for(auto& s:os)add(base,s.cover);
    vector<int> cand;
    auto put=[&](int x,int y){if(x>=0&&x<n&&y>=0&&y<n&&!taken[y*n+x])cand.push_back(y*n+x);};
    for(int i=0;i<n;i++){put(i,0);put(i,n-1);put(0,i);put(n-1,i);}
    for(int i=0;i<9;i++)for(int j=0;j<9;j++)put(i*(n-1)/8,j*(n-1)/8);
    for(int p:own)for(int dx=-1;dx<=1;dx++)for(int dy=-1;dy<=1;dy++)put(p%n+dx,p/n+dy);
    for(int p:enemy)for(int dx=-1;dx<=1;dx++)for(int dy=-1;dy<=1;dy++)put(p%n+dx,p/n+dy);
    if(n<=15)for(int x=0;x<n;x++)for(int y=0;y<n;y++)put(x,y);
    sort(cand.begin(),cand.end());cand.erase(unique(cand.begin(),cand.end()),cand.end());
    int result=cand.empty()?0:cand.front();double best=-1e30;
    for(int q:cand){
        P p=pt(q);Bits mine=base,theirs{};
        for(auto& s:es)if(!contains(p,s.p))add(theirs,s.cover);
        add(mine,shape({p},enemy).cover);
        for(int a=0;a<(int)own.size();a++){
            Shape s=shape({p,pt(own[a])},enemy);if(!s.p.empty())add(mine,s.cover);
            for(int b=0;b<a;b++){s=shape({p,pt(own[a]),pt(own[b])},enemy);if(!s.p.empty())add(mine,s.cover);}
        }
        double reach=0;
        for(int a:own){P t=pt(a);reach=max(reach,hypot(double(p.x-t.x),double(p.y-t.y))/n);}
        double value=size(mine)-1.12*size(theirs);
        value+=(own.size()<2?8.0:0.2)*reach;
        // Favor several usable large triangles over one readily blocked threat.
        if(own.size()>=2&&own.size()+1<(size_t)k){
            double area=0;
            for(int a=0;a<(int)own.size();a++)for(int b=0;b<a;b++){
                Shape s=shape({p,pt(own[a]),pt(own[b])},enemy);
                if(!s.p.empty())area=max(area,double(abs(cross(p,pt(own[a]),pt(own[b]))))/(n*n));
            }
            value+=0.3*area;
        }
        if(value>best+1e-9){best=value;result=q;}
    }
    return result;
}
static int field(const string&s,const string&key,int fallback=0){size_t p=s.find("\""+key+"\":");return p==string::npos?fallback:atoi(s.c_str()+p+key.size()+3);}
static vector<int> list(const string&s,const string&key){vector<int>v;size_t p=s.find("\""+key+"\":[");if(p==string::npos)return v;p+=key.size()+4;while(p<s.size()&&s[p]!=']'){if(isdigit(s[p])){char*end;v.push_back(strtol(s.c_str()+p,&end,10));p=end-s.c_str();}else p++;}return v;}
int main(){ios::sync_with_stdio(false);string line;pegband::BandPlan plan;size_t turn=0;while(getline(cin,line)){line.erase(remove_if(line.begin(),line.end(),[](unsigned char c){return isspace(c);}),line.end());if(line.find("\"type\":\"start\"")!=string::npos){n=field(line,"N",10);k=field(line,"pegs",5);r=field(line,"bands",5);samples.clear();int d=min(n,15);for(int y=0;y<d;y++)for(int x=0;x<d;x++)samples.push_back({x*(n-1)/max(1,d-1),y*(n-1)/max(1,d-1)});turn=0;cout<<"{\"ready\":true}"<<endl;}else if(line.find("\"type\":\"peg\"")!=string::npos){cout<<"{\"peg\":"<<peg(list(line,"your_pegs"),list(line,"their_pegs"))<<"}"<<endl;}else if(line.find("\"type\":\"band\"")!=string::npos){auto mine=list(line,"your_pegs");if(!turn)plan=pegband::solve_bands(n,mine,list(line,"their_pegs"),r,1.5);vector<int> band=turn<plan.bands.size()?plan.bands[turn]:vector<int>{mine.front()};turn++;cout<<"{\"band\":[";for(size_t i=0;i<band.size();i++){if(i)cout<<',';cout<<band[i];}cout<<"]}"<<endl;}else cout<<"{}"<<endl;} }
