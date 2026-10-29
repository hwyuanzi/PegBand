// Preserve the validated v1 wide-board placement policy.
// The main entry uses the upgraded planner for the final Blue placement.
#pragma once
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <numeric>
#include <utility>
#include <vector>
#include <unordered_map>

namespace classical_placement {
constexpr int WORDS=40;
struct Bits {
    std::array<uint64_t,WORDS> a{};
    void set(int p) { a[p>>6]|=uint64_t(1)<<(p&63); }
    void range(int lo,int hi) {
        if(lo>hi) return;
        int x=lo>>6,y=hi>>6;
        uint64_t l=~uint64_t(0)<<(lo&63),r=~uint64_t(0)>>(63-(hi&63));
        if(x==y) a[x]|=l&r;
        else { a[x]|=l; for(int j=x+1;j<y;j++) a[j]=~uint64_t(0); a[y]|=r; }
    }
    void add(const Bits& b,int w) { for(int i=0;i<w;i++) a[i]|=b.a[i]; }
    int count(int w) const { int s=0;for(int i=0;i<w;i++)s+=__builtin_popcountll(a[i]);return s; }
    int gain(const Bits& b,int w) const {int s=0;for(int i=0;i<w;i++)s+=__builtin_popcountll(a[i]&~b.a[i]);return s;}
};
struct P {int x,y;};
inline P point(int p,int n) { return {p%n,p/n}; }
inline int cross(P a,P b,P c){return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);}
inline bool contains(const std::array<P,3>& h,int size,P p) {
    if(size==1)return h[0].x==p.x&&h[0].y==p.y;
    if(size==2)return !cross(h[0],h[1],p)&&p.x>=std::min(h[0].x,h[1].x)&&p.x<=std::max(h[0].x,h[1].x)&&p.y>=std::min(h[0].y,h[1].y)&&p.y<=std::max(h[0].y,h[1].y);
    return cross(h[0],h[1],p)>=0&&cross(h[1],h[2],p)>=0&&cross(h[2],h[0],p)>=0;
}
inline int floor_div(int a,int b){int q=a/b,r=a%b;return q-(r<0);}
inline Bits raster(std::array<P,3> h,int size,int n) {
    Bits out;
    if(size==1){out.set(h[0].y*n+h[0].x);return out;}
    int lx=n,hx=0,ly=n,hy=0;
    for(int i=0;i<size;i++){lx=std::min(lx,h[i].x);hx=std::max(hx,h[i].x);ly=std::min(ly,h[i].y);hy=std::max(hy,h[i].y);}
    for(int y=ly;y<=hy;y++) {
        int lo=lx,hi=hx;
        for(int i=0;i<(size==2?2:3);i++) {
            P a=h[i],b=h[(i+1)%size];int dx=b.x-a.x,dy=b.y-a.y;
            int v=2*dx*(y-a.y)+2*dy*a.x+std::abs(dx)+std::abs(dy);
            if(dy>0)hi=std::min(hi,floor_div(v-1,2*dy));
            else if(dy<0)lo=std::max(lo,floor_div(-v,-2*dy)+1);
            else if(v<=0){hi=-1;break;}
        }
        if(lo<=hi)out.range(y*n+lo,y*n+hi);
    }
    return out;
}
struct Shape {std::array<P,3> h;int size;Bits cover;};
inline bool make_shape(const std::vector<int>& ids,const std::vector<int>& enemy,int n,Shape& s) {
    s.size=static_cast<int>(ids.size());
    for(int i=0;i<s.size;i++)s.h[i]=point(ids[i],n);
    if(s.size==3) {
        int c=cross(s.h[0],s.h[1],s.h[2]);
        if(!c)return false;
        if(c<0)std::swap(s.h[1],s.h[2]);
    }
    for(int e:enemy)if(contains(s.h,s.size,point(e,n)))return false;
    s.cover=raster(s.h,s.size,n);
    for(int e:enemy)s.cover.a[e>>6]&=~(uint64_t(1)<<(e&63));
    return true;
}
struct Side {
    std::vector<int> pegs,enemy;
    std::vector<Shape> shapes;
    Bits reach;
    int n,w;
    Side(int board,const std::vector<int>& p,const std::vector<int>& e):pegs(p),enemy(e),n(board),w((board*board+63)/64) {
        Shape s;
        for(size_t i=0;i<p.size();i++) {
            if(make_shape({p[i]},e,n,s)){shapes.push_back(s);reach.add(s.cover,w);}
            for(size_t j=0;j<i;j++) {
                if(make_shape({p[i],p[j]},e,n,s)){shapes.push_back(s);reach.add(s.cover,w);}
                for(size_t k=0;k<j;k++)if(make_shape({p[i],p[j],p[k]},e,n,s)){shapes.push_back(s);reach.add(s.cover,w);}
            }
        }
    }
    Bits after_add(int q,std::vector<Bits>* options=nullptr) const {
        Bits b=reach;Shape s;
        if(options){options->reserve(shapes.size()+pegs.size()*pegs.size()/2+1);for(const auto& t:shapes)options->push_back(t.cover);}
        auto push=[&](std::vector<int> ids){if(make_shape(ids,enemy,n,s)){b.add(s.cover,w);if(options)options->push_back(s.cover);}};
        push({q});
        for(size_t i=0;i<pegs.size();i++){
            push({q,pegs[i]});
            for(size_t j=0;j<i;j++)push({q,pegs[i],pegs[j]});
        }
        return b;
    }
    Bits after_block(int q,std::vector<Bits>* options=nullptr)const {
        Bits b;P p=point(q,n);
        if(options)options->reserve(shapes.size());
        for(const auto& s:shapes)if(!contains(s.h,s.size,p)){b.add(s.cover,w);if(options)options->push_back(s.cover);}
        b.a[q>>6]&=~(uint64_t(1)<<(q&63));
        return b;
    }
};
inline double limited_score(const Bits& reach,const std::vector<Bits>& options,int r,int w) {
    if(options.empty())return 0;
    Bits used;int score=0;
    for(int t=0;t<r;t++){
        int best=-1,gain=0;
        for(int j=0;j<static_cast<int>(options.size());j++){int g=options[j].gain(used,w);if(g>gain){gain=g;best=j;}}
        if(best<0)break;
        used.add(options[best],w);score+=gain;
    }
    // Extra hull vertices can improve on a triangle; retain an optimistic component.
    return .85*score+.15*reach.count(w);
}
struct Scored {double value;int p;};
class Search {
    int n,k,r,w;
    std::chrono::steady_clock::time_point deadline;
    mutable std::unordered_map<uint64_t,double> terminal_cache;
    bool timed()const{return std::chrono::steady_clock::now()>=deadline;}
    double structure(const std::vector<int>& mine,int q)const {
        // A potential peg must still support future play when fewer than three pegs exist.
        P p=point(q,n);double d=n*n;
        for(int a:mine){P t=point(a,n);d=std::min(d,double((p.x-t.x)*(p.x-t.x)+(p.y-t.y)*(p.y-t.y)));}
        double edge=std::min({p.x,p.y,n-1-p.x,n-1-p.y});
        int left=k-static_cast<int>(mine.size())-1;
        double phase=left/double(std::max(1,k-1));
        double value=phase*(.055*std::sqrt(d)*n-.035*edge*n);
        if(mine.size()<2)value+=.09*std::sqrt(d)*n-.07*edge*n;
        return value;
    }
    std::vector<int> candidates(const std::vector<int>& a,const std::vector<int>& b,bool full)const {
        std::vector<bool> taken(n*n),seen(n*n);for(int p:a)taken[p]=true;for(int p:b)taken[p]=true;
        std::vector<int> c;
        auto add=[&](int x,int y){if(x>=0&&y>=0&&x<n&&y<n){int p=y*n+x;if(!taken[p]&&!seen[p]){seen[p]=true;c.push_back(p);}}};
        for(int i=0;i<7;i++)for(int j=0;j<7;j++)add((i*(n-1)+3)/6,(j*(n-1)+3)/6);
        std::vector<int> both=a;both.insert(both.end(),b.begin(),b.end());
        for(int p:both){P t=point(p,n);for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++)add(t.x+dx,t.y+dy);}
        for(size_t i=0;i<both.size();i++)for(size_t j=0;j<i;j++){P p=point(both[i],n),q=point(both[j],n);add((p.x+q.x)/2,(p.y+q.y)/2);}
        if(full)for(int p=0;p<n*n;p++)if(!taken[p]&&!seen[p])c.push_back(p);
        return c;
    }
    std::vector<Scored> rank(const std::vector<int>& a,const std::vector<int>& b,bool full,int limit)const {
        Side own(n,a,b),enemy(n,b,a);std::vector<Scored> out;
        auto cand=candidates(a,b,full);out.reserve(cand.size());
        for(int q:cand) {
            std::vector<Bits> os,es;
            bool limited=r<static_cast<int>(std::max(a.size()+1,b.size()))/2;
            Bits x=own.after_add(q,limited?&os:nullptr),y=enemy.after_block(q,limited?&es:nullptr);
            double my=limited?limited_score(x,os,r,w):x.count(w);
            double en=limited?limited_score(y,es,r,w):y.count(w);
            double value=my-en+structure(a,q);
            out.push_back({value,q});
            if((out.size()&31)==0&&timed())break;
        }
        std::sort(out.begin(),out.end(),[](const Scored&x,const Scored&y){return x.value!=y.value?x.value>y.value:x.p<y.p;});
        if(static_cast<int>(out.size())<=limit)return out;
        // Nearby cells frequently have the same tactical idea. Keep a few precise
        // leaders, then reserve beam slots for different regions of the board.
        std::vector<Scored> diverse;
        int radius=std::max(1,n/9);
        for(const auto& s:out) {
            bool near=false;
            for(const auto& t:diverse) {
                P p=point(s.p,n),q=point(t.p,n);
                if(std::abs(p.x-q.x)+std::abs(p.y-q.y)<radius){near=true;break;}
            }
            if(diverse.size()<2||!near)diverse.push_back(s);
            if(static_cast<int>(diverse.size())==limit)break;
        }
        for(const auto& s:out) {
            if(static_cast<int>(diverse.size())==limit)break;
            if(std::none_of(diverse.begin(),diverse.end(),[&](const Scored& t){return t.p==s.p;}))diverse.push_back(s);
        }
        return diverse;
    }
    double final_value(const std::vector<int>& a,const std::vector<int>& b)const {
        uint64_t key=1469598103934665603ULL;
        std::vector<int> sa=a,sb=b;std::sort(sa.begin(),sa.end());std::sort(sb.begin(),sb.end());
        for(int p:sa)key=(key^uint64_t(p+1))*1099511628211ULL;
        key=(key^uint64_t(4095))*1099511628211ULL;
        for(int p:sb)key=(key^uint64_t(p+1))*1099511628211ULL;
        auto found=terminal_cache.find(key);if(found!=terminal_cache.end())return found->second;
        auto x=pegband::solve_bands(n,a,b,r,.012),y=pegband::solve_bands(n,b,a,r,.012);
        double result=x.score-y.score;terminal_cache.emplace(key,result);return result;
    }
    double visit(const std::vector<int>& a,const std::vector<int>& b,int depth,double alpha,double beta)const {
        if(timed())return 0;
        if(static_cast<int>(a.size())>=k) {
            if(static_cast<int>(b.size())>=k)return final_value(a,b);
            return -visit(b,a,depth, -beta,-alpha);
        }
        bool terminal=static_cast<int>(a.size())==k-1&&static_cast<int>(b.size())==k;
        auto moves=rank(a,b,terminal,terminal?24:(depth<=1?1:6));
        if(moves.empty())return 0;
        if(depth<=1&&!terminal)return moves[0].value;
        double best=-1e100;
        for(const auto& s:moves) {
            std::vector<int> aa=a;aa.push_back(s.p);
            double value=terminal?final_value(aa,b):-visit(b,aa,depth-1,-beta,-alpha);
            if(timed())return 0;
            best=std::max(best,value);alpha=std::max(alpha,value);
            if(alpha>=beta)break;
        }
        return best;
    }
public:
    Search(int board,int pegs,int bands,double seconds):n(board),k(pegs),r(bands),w((board*board+63)/64),deadline(std::chrono::steady_clock::now()+std::chrono::milliseconds(int(seconds*1000))){}
    int choose(const std::vector<int>& a,const std::vector<int>& b) {
        auto root=rank(a,b,true,static_cast<int>(b.size())>=k?48:24);
        if(root.empty())return 0;
        if(k==1)return root[0].p;
        if(a.size()<2&&k>=3) {
            Side own(n,a,b),enemy(n,b,a);
            for(int y:{0,(n-1)/2,n-1})for(int x:{0,(n-1)/2,n-1}) {
                int p=y*n+x;
                if(std::find(a.begin(),a.end(),p)!=a.end()||std::find(b.begin(),b.end(),p)!=b.end())continue;
                if(std::any_of(root.begin(),root.end(),[&](const Scored&s){return s.p==p;}))continue;
                double v=own.after_add(p).count(w)-enemy.after_block(p).count(w)+structure(a,p);
                root.push_back({v,p});
            }
        }
        int answer=root[0].p;
        int remaining=2*k-static_cast<int>(a.size()+b.size());
        if(static_cast<int>(b.size())>=k) {
            double best=-1e100;
            // Small last-move positions are cheap enough to compare every
            // free square using the actual finite-band score.
            if(n<=12&&k<=6) {
                root.clear();for(int p:candidates(a,b,true))root.push_back({0,p});
            }
            for(const auto& s:root) {
                std::vector<int> aa=a;aa.push_back(s.p);double v=final_value(aa,b);
                if(v>best){best=v;answer=s.p;}
                if(timed())break;
            }
            return answer;
        }
        // Iterative deepening gives every root candidate the same completed
        // horizon. Discard the partial iteration when its deadline is reached.
        int maxdepth=std::min(remaining,k<=8?7:5);
        for(int depth=2;depth<=maxdepth;depth++) {
            double best=-1e100;int candidate=answer;bool complete=true;
            std::vector<Scored> reordered;
            for(const auto& s:root) {
                std::vector<int> aa=a;aa.push_back(s.p);
                double value=-visit(b,aa,depth-1,-1e100,-best);
                if(timed()){complete=false;break;}
                // The static score only breaks equal lookahead values.
                value+=s.value*.00001;
                reordered.push_back({value,s.p});
                if(value>best){best=value;candidate=s.p;}
            }
            if(!complete)break;
            answer=candidate;
            std::stable_sort(reordered.begin(),reordered.end(),[](const Scored&x,const Scored&y){return x.value>y.value;});
            // Preserve the static scores, while trying the previous best first.
            std::vector<Scored> ordered;
            for(const auto& x:reordered)for(const auto& s:root)if(s.p==x.p)ordered.push_back(s);
            root=std::move(ordered);
        }
        return answer;
    }
};
} // namespace classical_placement
